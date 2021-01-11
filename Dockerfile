FROM fedora:33
  
LABEL maintainer="Hein-Pieter van Braam-Stewart <hp@prehensile-tales.com>"

RUN dnf -y install python3-pip git && \
    dnf clean all && \
    pip3 install python-keycloak git+https://github.com/jeblair/giteapy@v1.12.0

COPY sync.py /root/sync.py
WORKDIR /root

CMD /root/sync.py

