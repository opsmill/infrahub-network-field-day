# The firewall half of the access broker.
#
# hostNetwork is what makes this work at all: the firewall's management address
# is on containerlab's management bridge, which pods on the fabric have no route
# to. Sharing the node's network namespace puts the controller on that bridge
# the same way any real automation host would be.
FROM python:3.12.14-slim

# paramiko is the only dependency. Everything else -- the Kubernetes client, the
# JSON, the retry loop -- is stdlib, which keeps this image small enough to
# import into three k3s nodes without thinking about it.
RUN pip install --no-cache-dir "paramiko==3.5.0"

COPY controller.py /opt/controller.py
USER 65532
ENTRYPOINT ["python3", "-u", "/opt/controller.py"]
