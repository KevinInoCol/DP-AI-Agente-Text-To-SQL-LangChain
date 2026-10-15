Coloca aquí la clave JSON de la Service Account de Google Cloud
y apunta a ella en .env:

    GOOGLE_APPLICATION_CREDENTIALS=credentials/<tu-clave>.json

Esta carpeta está en .gitignore: la clave NUNCA se sube al repo.

Permisos que necesita la Service Account (en SU proyecto de GCP):
  - roles/bigquery.jobUser   (ejecutar consultas; se facturan en ese proyecto)
  - BigQuery API habilitada en ese proyecto
El dataset público bigquery-public-data.new_york_citibike ya es legible por
cualquiera: no hace falta darle permisos sobre él.
