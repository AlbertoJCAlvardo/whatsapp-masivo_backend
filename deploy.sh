#!/bin/bash

PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${CLOUD_RUN_REGION:-us-central1}"
SERVICE_NAME="whatsapp-api"

gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

gcloud run deploy $SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID" \
    --set-env-vars "WHATSAPP_PHONE_NUMBER_ID=$WHATSAPP_PHONE_NUMBER_ID" \
    --set-env-vars "WHATSAPP_ACCESS_TOKEN=$WHATSAPP_ACCESS_TOKEN" \
    --set-env-vars "WHATSAPP_VERIFY_TOKEN=$WHATSAPP_VERIFY_TOKEN" \
    --set-env-vars "BIGQUERY_DATASET=${BIGQUERY_DATASET:-whatsapp_messages}"



