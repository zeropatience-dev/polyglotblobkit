"""Minimal single-tenant deployment factory. Multi-tenant deployments supply their own factory."""
import os
from pathlib import Path
from polyglotblobkit import Config
from polyglotblobkit.security import Binding, Grant, Identity, RS256Verifier, TenantGateway, TenantPolicy
from polyglotblobkit.storage import AzureFilenameStorage, S3FilenameStorage, MinioFilenameStorage
from .api import create_app as make_app


def create_app():
    env = os.environ
    tenant = env['PBK_TENANT']
    issuer, audience, subject = (env[k] for k in ('PBK_ISSUER', 'PBK_AUDIENCE', 'PBK_SUBJECT'))
    config = Config.load(env['PBK_CONFIG'])
    verifier = RS256Verifier(public_key_pem=Path(env['PBK_PUBLIC_KEY_FILE']).read_bytes(), issuer=issuer, audience=audience)
    provider = env['PBK_PROVIDER']
    if provider == 'azure':
        from azure.storage.blob import ContainerClient
        client = ContainerClient.from_connection_string(env['AZURE_STORAGE_CONNECTION_STRING'], env['PBK_CONTAINER'])
        storage = AzureFilenameStorage.from_config(client, config)
    elif provider in ('s3', 'minio'):
        import boto3
        from botocore.config import Config as SDKConfig
        endpoint = env['PBK_S3_ENDPOINT'] if provider == 'minio' else None
        client = boto3.client('s3', endpoint_url=endpoint, config=SDKConfig(s3={'addressing_style':'path' if endpoint else 'auto'}))
        cls = MinioFilenameStorage if provider == 'minio' else S3FilenameStorage
        storage = cls.from_config(client, env['PBK_BUCKET'], config)
    else:
        raise ValueError('Unsupported configured provider')
    gateway = TenantGateway(verifier=verifier,
        bindings=[Binding(TenantPolicy(tenant, config, int(env.get('PBK_REQUESTS_PER_MINUTE','60'))), env['PBK_RESOURCE_ID'], storage)],
        grants=[Grant(Identity(issuer,subject), tenant, frozenset(env['PBK_PERMISSIONS'].split(',')))])
    app = make_app(gateway, max_concurrent_uploads=int(env.get('PBK_CONCURRENT_UPLOADS','4')))
    @app.on_event('shutdown')
    def close_client():
        client.close()
    return app
