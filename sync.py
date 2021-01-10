#!/usr/bin/env python3

import os
import time
import giteapy
from giteapy.rest import ApiException
from pprint import pprint
import random
import string

from keycloak import KeycloakAdmin

PROTECTED_USERS=['gitea']

SYNC_INTERVAL_SECONDS=int(os.environ.get('SYNC_INTERVAL_SECONDS'))

KEYCLOAK_USERNAME=os.environ.get('KEYCLOAK_USERNAME')
KEYCLOAK_PASSWORD=os.environ.get('KEYCLOAK_PASSWORD')
KEYCLOAK_URL=os.environ.get('KEYCLOAK_URL')
KEYCLOAK_REALM=os.environ.get('KEYCLOAK_REALM')
KEYCLOAK_CLIENT_SECRET=os.environ.get('KEYCLOAK_CLIENT_SECRET')

GITEA_URL=os.environ.get('GITEA_URL')
GITEA_API_KEY=os.environ.get('GITEA_API_KEY')

keycloak_admin = KeycloakAdmin(
    server_url=KEYCLOAK_URL,
    username=KEYCLOAK_USERNAME,
    password=KEYCLOAK_PASSWORD,
    realm_name=KEYCLOAK_REALM,
    client_secret_key=KEYCLOAK_CLIENT_SECRET,
    verify=True)

# Configure API key authorization: AccessToken
configuration = giteapy.Configuration()
configuration.host = GITEA_URL
configuration.api_key['access_token'] = GITEA_API_KEY

# create an instance of the API class
gitea_admin = giteapy.AdminApi(giteapy.ApiClient(configuration))
gitea_org = giteapy.OrganizationApi(giteapy.ApiClient(configuration))

def get_random_string(length):
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str

def get_keycloak_users():
    users = keycloak_admin.get_users({})
    for user in users:
        user_groups = keycloak_admin.get_user_groups(user_id=user['id'])
        user['groups'] = []
        for group in user_groups:
            user['groups'].append(group['name'])

    return users

def get_gitea_users():
    try:
        api_response = gitea_admin.admin_get_all_users()
        return api_response
    except ApiException as e:
        print("Exception when calling AdminApi->admin_get_all_users: %s\n" % e) 
        return None

def disable_gitea_user(gitea_user):
    body = giteapy.EditUserOption(
        active=False,
        admin=False,
        prohibit_login=True,
        email=gitea_user.email,
        login_name=gitea_user.login
    )
    api_response = gitea_admin.admin_edit_user(gitea_user.login, body=body)

def update_gitea_user(keycloak_user):
    try:
        body = giteapy.EditUserOption(
            active=True,
            prohibit_login=False,
            admin='gitea-admin' in keycloak_user['groups'],
            allow_create_organization='gitea-admin' in keycloak_user['groups'],
            email=keycloak_user['email'],
            full_name=keycloak_user['attributes']['name'][0],
            login_name=keycloak_user['id'],
            password=get_random_string(20),
            must_change_password=False,
            source_id=2
        )
    except KeyError:
        return
    api_response = gitea_admin.admin_edit_user(keycloak_user['username'], body=body)

def create_gitea_user(keycloak_user):
    try:
        body = giteapy.CreateUserOption(
            email=keycloak_user['email'],
            full_name=keycloak_user['attributes']['name'][0],
            login_name=keycloak_user['id'],
            password=get_random_string(20),
            username=keycloak_user['username'],
            must_change_password=False,
            source_id=2
        )
    except KeyError:
        return
    api_response = gitea_admin.admin_create_user(body=body)

def get_gitea_members_team(organization):
    teams = gitea_org.org_list_teams(organization)
    for team in teams:
        if team.name == 'Members':
            return team.id

    return None

def get_gitea_organizations():
    limit = 10
    page = 0
    organizations = []
    while True:
        page += 1
        api_response = gitea_admin.admin_get_all_orgs(page=page, limit=limit)
        organizations.extend(api_response)
        if (len(api_response) < limit):
            break

    retval = []
    for organization in organizations:
        members_id = get_gitea_members_team(organization.username)
        members = gitea_org.org_list_team_members(members_id)

        usernames = []
        for member in members:
            usernames.append(member.login)
                
        retval.append({'organization': organization, 'members': usernames})
    return retval

def create_gitea_organization(keycloak_group):
    body = giteapy.CreateOrgOption(
        username=keycloak_group['name'],
        visibility='private',
    )
    api_response = gitea_admin.admin_create_org('gitea', body)

    body = giteapy.CreateTeamOption(
        name="Members",
        permission='write',
        units=['repo.code',
           'repo.issues',
           'repo.pulls',
           'repo.releases',
           'repo.wiki',
           'repo.ext_wiki',
           'repo.ext_issues',
           'repo.projects']
    )
    api_response = gitea_org.org_create_team(keycloak_group['name'], body=body)

def add_user_to_gitea_organization(organization, login):
    team_id = get_gitea_members_team(organization)

    if team_id == None:
        print(f"Couldn't find the 'Members' team for organization {organization}")
        return

    gitea_org.org_add_team_member(team_id, login)

def delete_user_from_gitea_organization(organization, login):
    team_id = get_gitea_members_team(organization)

    if team_id == None:
        print(f"Couldn't find the 'Members' team for organization {organization}")
        return

    gitea_org.org_remove_team_member(team_id, login)

def get_keycloak_groups():
    groups = keycloak_admin.get_groups()
    retval = []
    for group in groups:
        g = keycloak_admin.get_group(group['id'])
        retval.append(g)

    return retval

def sync():
    ku = get_keycloak_users()
    gu = get_gitea_users()

    for keycloak_user in ku:
        found = False
        disabled = False
        for gitea_user in gu:
            if gitea_user.login == keycloak_user['username']:
                found = True
                if not keycloak_user['enabled']:
                    disabled = True
                break

        if not found:
            print(f"User {keycloak_user['username']} does not exist in gitea")
            create_gitea_user(keycloak_user)
            update_gitea_user(keycloak_user)
        elif not disabled:
            print(f"Updating user {keycloak_user['username']}")
            if keycloak_user['enabled']:
                update_gitea_user(keycloak_user)

    gu = get_gitea_users()

    for gitea_user in gu:
        found = False
        disabled = False

        for keycloak_user in ku:
            if gitea_user.login == keycloak_user['username']:
                found = True
                if not keycloak_user['enabled']:
                    disabled = True
                break

        if not found and gitea_user.login not in PROTECTED_USERS:
            print(f"User {gitea_user.login} found in gitea but does not exist in keycloak")
            disable_gitea_user(gitea_user)

        if disabled:
            print(f"User {gitea_user.login} disabled in keycloak")
            disable_gitea_user(gitea_user)

    organizations = get_gitea_organizations()
    keycloak_groups = get_keycloak_groups()

    for group in keycloak_groups:
        found = False
        try:
            if 'customer' in group['attributes']['businessCategory']:
                for org in organizations:
                    if org['organization'].username == group['name']:
                        found = True
        except KeyError:
            found = True

        if not found:
            print(f"Organization {group['name']} not found, creating")
            create_gitea_organization(group)

    organizations = get_gitea_organizations()

    for organization in organizations:
        expected_members = []
        for keycloak_user in ku:
            if organization['organization'].username in keycloak_user['groups']:
                expected_members.append(keycloak_user['username'])
        
        for expected_member in expected_members:
            if not expected_member in organization['members']:
                print(f"Adding user {expected_member} to organization {organization['organization'].username}")
                add_user_to_gitea_organization(organization['organization'].username, expected_member)

        for member in organization['members']:
            if member not in expected_members:
                print(f"Removing user {member} from organziation {organization['organization'].username}")
                delete_user_from_gitea_organization(organization['organization'].username, member)

while True:
    try:
        sync()
    except Exception as e:
        print(e)

    print("Sleeping")
    time.sleep(SYNC_INTERVAL_SECONDS)
    
