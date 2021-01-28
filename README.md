# Simple tool to synchronize gitea with keycloak

This tool will synchronize Gitea project memberships (and create projects) based on group memberships in Keycloak. This allows a seemless login flow through OAuth2 with Keycloak.

Groups with the 'businessCategory' of 'customer' are created in Gitea. Users in such groups are created (or updated in) in Gitea.

It is recommended to run this tool as a container. The following environment variables are required as configuration:

 * `SYNC_INTERVAL_SECONDS` - How many seconds to wait between each sync run
 * `KEYCLOAK_USERNAME` - Username of a keycloak user with direct grant and `cli` rights
 * `KEYCLOAK_PASSWORD` - Password of the above user

 * `KEYCLOAK_URL` - URL of the Keycloak server
 * `KEYCLOAK_REALM` - Realm that contains the users and groups to be synchronzied
 * `KEYCLOAK_CLIENT_SECRET` - Client secret for keycloak service to login as.

 * `GITEA_URL` - URL to Gitea
 * `GITEA_API_KEY` - API key for Gitea (requires admin account)

# Requirements

 * A user in Gitea called `gitea` with admin rights. This user will also own all repositories the sync tool creates
 * A user in Keycloak with access to a client in keycloak with `cli` rights
 * The BusinessCategory attributes on the relavant groups
