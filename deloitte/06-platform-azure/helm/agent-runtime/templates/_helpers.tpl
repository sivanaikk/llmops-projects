{{- define "agent.labels" -}}
app.kubernetes.io/name: agent-runtime
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
{{- define "agent.selector" -}}
app.kubernetes.io/name: agent-runtime
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
