#!/usr/bin/env python3
"""Authorized synthetic R2 checks; preserve ownership markers and delete only this run's test objects."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import secrets
import sys
from urllib import error, request

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from ops import Blocked, ROOT, load, validate_target


def main():
    stage = 'configuration'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, type=Path)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--credential-set', choices=('active', 'rotation'), default='active')
    args = parser.parse_args()
    try:
        validate_target(load(args.target))
        manifest = load(ROOT / 'infra/deployment-manifest.yml')
        owner = manifest['ownership_marker']
        account = manifest['cloudflare']['account_id']
        if args.dry_run:
            print('NOT_EXECUTED: bucket ownership, synthetic upload/download, signed URL, S3 API anonymous and cross-token denial')
            return 0
        clients = {}
        for kind in ('media', 'backups'):
            suffix = '.rotation' if args.credential_set == 'rotation' else ''
            filename = ROOT / '.ops-private/secrets' / ('r2-' + kind + suffix + '.json')
            if filename.stat().st_mode & 0o077 or filename.is_symlink():
                raise Blocked('R2 credential file must be regular and mode 0600')
            credential = load(filename)
            bucket = 'hablas-evo-staging-' + kind
            endpoint = 'https://' + account + '.r2.cloudflarestorage.com'
            if credential['owner'] != owner or credential['account_id'] != account \
                    or credential['bucket'] != bucket or credential['endpoint'] != endpoint:
                raise Blocked('R2 credential identity mismatch')
            client = boto3.client('s3', endpoint_url=endpoint, region_name='auto',
                aws_access_key_id=credential['access_key_id'], aws_secret_access_key=credential['secret_access_key'],
                config=Config(signature_version='s3v4', connect_timeout=10, read_timeout=20,
                              retries={'max_attempts': 1}, s3={'addressing_style': 'path'}))
            clients[kind] = client
            marker = '.ops/ownership.json'
            stage = kind + ': list ownership'
            objects = client.list_objects_v2(Bucket=bucket, Prefix=marker, MaxKeys=2).get('Contents', [])
            if objects:
                stage = kind + ': verify ownership'
                value = json.loads(client.get_object(Bucket=bucket, Key=marker)['Body'].read())
                if value != {'owner': owner, 'account_id': account, 'bucket': bucket}:
                    raise Blocked('Bucket ownership marker differs')
            else:
                stage = kind + ': adopt empty bucket'
                if client.list_objects_v2(Bucket=bucket, MaxKeys=1).get('Contents'):
                    raise Blocked('Unmarked bucket is not empty; refusing adoption')
                client.put_object(Bucket=bucket, Key=marker, IfNoneMatch='*', ContentType='application/json',
                                  Body=json.dumps({'owner': owner, 'account_id': account, 'bucket': bucket}).encode())
            key = '.ops/tests/' + secrets.token_hex(16) + '.bin'
            data = secrets.token_bytes(65536)
            uploaded = False
            try:
                stage = kind + ': upload'
                client.put_object(Bucket=bucket, Key=key, Body=data, ContentType='application/octet-stream', IfNoneMatch='*')
                uploaded = True
                stage = kind + ': download checksum'
                restored = client.get_object(Bucket=bucket, Key=key)['Body'].read()
                if hashlib.sha256(restored).digest() != hashlib.sha256(data).digest():
                    raise Blocked('R2 object checksum mismatch')
                stage = kind + ': signed download'
                signed = client.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': key}, ExpiresIn=60)
                with request.urlopen(request.Request(signed, headers={'User-Agent': 'hablas-evo-r2-test/1.0'}), timeout=20) as response:
                    if response.read() != data:
                        raise Blocked('Signed download differs')
                stage = kind + ': S3 API anonymous denial'
                try:
                    request.urlopen(request.Request(endpoint + '/' + bucket + '/' + key,
                        headers={'User-Agent': 'hablas-evo-r2-test/1.0'}), timeout=20)
                    raise Blocked('Anonymous object access unexpectedly allowed')
                except error.HTTPError as exc:
                    body = exc.read(8192).decode('utf-8', 'replace')
                    code = re.search(r'<Code>([A-Za-z0-9]+)</Code>', body)
                    if exc.code not in (401, 403) and not (exc.code == 400 and code and code.group(1) in
                                                           ('InvalidArgument', 'InvalidRequest', 'AuthorizationHeaderMalformed')):
                        raise Blocked('Anonymous denial returned HTTP ' + str(exc.code)
                                      + '/S3-' + (code.group(1) if code else 'unknown')) from None
                print(json.dumps({'status': 'PASS', 'bucket': bucket, 'bytes': len(data),
                                  'upload_download_checksum': True, 'signed_download': True,
                                  's3_api_anonymous_denied': True}))
            finally:
                if uploaded:
                    client.delete_object(Bucket=bucket, Key=key)
        for kind, other in (('media', 'backups'), ('backups', 'media')):
            stage = kind + ': cross-bucket denial'
            try:
                clients[kind].list_objects_v2(Bucket='hablas-evo-staging-' + other, MaxKeys=1)
                raise Blocked('A credential can access the other bucket')
            except ClientError as exc:
                if exc.response['ResponseMetadata']['HTTPStatusCode'] != 403:
                    raise Blocked('Cross-bucket denial inconclusive') from None
            print('PASS: ' + kind + ' credential cannot access ' + other + ' bucket')
        return 0
    except (Blocked, ClientError, OSError, ValueError, KeyError) as exc:
        code = exc.response.get('Error', {}).get('Code', 'unknown') if isinstance(exc, ClientError) else type(exc).__name__
        detail = str(exc) if isinstance(exc, Blocked) else code
        print('BLOCKED: R2 ' + stage + ' failed (' + detail + '); credentials and signed URLs suppressed', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
