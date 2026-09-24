targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Nama lingkungan, dipakai sebagai awalan nama sumber daya.')
param environmentName string

@minLength(1)
@description('Region Azure. Pastikan model yang dipilih tersedia di region ini.')
param location string

@description('Nama model multimodal di katalog Foundry. Jangan memakai keluarga GPT-4.')
param modelName string = 'gpt-5-mini'

@description('Versi model. Kosongkan agar Azure memakai versi bawaan.')
param modelVersion string = '2025-08-07'

@description('Kapasitas deployment model dalam ribuan token per menit.')
param modelCapacity int = 10

var tags = { 'azd-env-name': environmentName }

resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module resources 'resources.bicep' = {
  name: 'resources'
  scope: rg
  params: {
    environmentName: environmentName
    location: location
    tags: tags
    modelName: modelName
    modelVersion: modelVersion
    modelCapacity: modelCapacity
  }
}

output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = rg.name

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.registryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = resources.outputs.registryName
output AZURE_CONTAINER_APPS_ENVIRONMENT_ID string = resources.outputs.environmentId
output AZURE_CONTAINER_APPS_ENVIRONMENT_NAME string = resources.outputs.environmentName

output AZURE_AI_ENDPOINT string = resources.outputs.aiEndpoint
output AZURE_AI_DEPLOYMENT string = resources.outputs.aiDeployment
output AZURE_MAPS_CLIENT_ID string = resources.outputs.mapsClientId
output SERVICE_WEB_URI string = resources.outputs.webUri
