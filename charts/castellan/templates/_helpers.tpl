{{/*
Base chart name.
*/}}
{{- define "castellan.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Fully qualified app name.
*/}}
{{- define "castellan.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "castellan.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "castellan.labels" -}}
helm.sh/chart: {{ include "castellan.chart" . }}
{{ include "castellan.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "castellan.selectorLabels" -}}
app.kubernetes.io/name: {{ include "castellan.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "castellan.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "castellan.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/*
Mongo connection env vars, sourced from the pre-existing Secrets.
*/}}
{{- define "castellan.mongoEnv" -}}
- name: MONGODB_HOST
  valueFrom:
    secretKeyRef:
      name: {{ required "mongodb.connectionString.secretName is required" .Values.mongodb.connectionString.secretName }}
      key: {{ .Values.mongodb.connectionString.secretKey }}
{{- if .Values.mongodb.credentials.secretName }}
- name: CASTELLAN_DB_USER
  valueFrom:
    secretKeyRef:
      name: {{ .Values.mongodb.credentials.secretName }}
      key: {{ .Values.mongodb.credentials.usernameKey }}
- name: CASTELLAN_DB_PASS
  valueFrom:
    secretKeyRef:
      name: {{ .Values.mongodb.credentials.secretName }}
      key: {{ .Values.mongodb.credentials.passwordKey }}
{{- end -}}
{{- end -}}