# The access portal. One file, no dependencies beyond the standard library --
# the catalog arrives as a mounted ConfigMap and every other piece of state
# lives in the Kubernetes API, so there is nothing here to persist.
FROM python:3.12.14-slim
COPY portal.py /opt/portal.py
USER 65532
EXPOSE 8080
ENTRYPOINT ["python3", "-u", "/opt/portal.py"]
