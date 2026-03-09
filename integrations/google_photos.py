import json
from pathlib import Path
from typing import Iterator, Optional

from utils.constants import GOOGLE_PHOTOS_SCOPES, TOKEN_PATH


class GooglePhotosClient:
    BASE_URL = 'https://photoslibrary.googleapis.com/v1'

    def __init__(self, credentials_path: str):
        self.credentials_path = credentials_path
        self._session = None
        self._creds = None

    def authenticate(self) -> bool:
        """Run OAuth2 flow and save token. Returns True on success."""
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.oauth2.credentials import Credentials
            import google.auth.transport.requests

            token_file = TOKEN_PATH

            # Try loading existing token
            if token_file.exists():
                try:
                    creds = Credentials.from_authorized_user_file(str(token_file), GOOGLE_PHOTOS_SCOPES)
                    if creds and creds.valid:
                        self._creds = creds
                        self._build_session()
                        return True
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(google.auth.transport.requests.Request())
                        self._save_token(creds)
                        self._creds = creds
                        self._build_session()
                        return True
                except Exception:
                    pass

            # New OAuth flow
            if not Path(self.credentials_path).exists():
                raise FileNotFoundError(
                    f'Arquivo de credenciais não encontrado: {self.credentials_path}\n'
                    'Baixe o client_secret.json do Google Cloud Console e salve em assets/'
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_path, GOOGLE_PHOTOS_SCOPES
            )
            creds = flow.run_local_server(port=0)
            self._save_token(creds)
            self._creds = creds
            self._build_session()
            return True

        except Exception as e:
            print(f'Erro na autenticação Google Photos: {e}')
            return False

    def _save_token(self, creds):
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())

    def _build_session(self):
        import requests
        from google.auth.transport.requests import AuthorizedSession
        self._session = AuthorizedSession(self._creds)

    def _get(self, endpoint: str, params: dict = None) -> dict:
        if not self._session:
            raise RuntimeError('Not authenticated. Call authenticate() first.')
        import requests
        resp = self._session.get(f'{self.BASE_URL}/{endpoint}', params=params or {})
        resp.raise_for_status()
        return resp.json()

    def _post(self, endpoint: str, json_data: dict = None) -> dict:
        if not self._session:
            raise RuntimeError('Not authenticated.')
        resp = self._session.post(f'{self.BASE_URL}/{endpoint}', json=json_data or {})
        resp.raise_for_status()
        return resp.json()

    def list_albums(self) -> list[dict]:
        """List all Google Photos albums."""
        albums = []
        page_token = None
        while True:
            params = {'pageSize': 50}
            if page_token:
                params['pageToken'] = page_token
            data = self._get('albums', params)
            albums.extend(data.get('albums', []))
            page_token = data.get('nextPageToken')
            if not page_token:
                break
        return albums

    def list_media_items(self, album_id: Optional[str] = None, page_size: int = 100) -> Iterator[dict]:
        """Iterate over media items, optionally filtered by album."""
        page_token = None
        while True:
            if album_id:
                body = {'albumId': album_id, 'pageSize': page_size}
                if page_token:
                    body['pageToken'] = page_token
                data = self._post('mediaItems:search', body)
            else:
                params = {'pageSize': page_size}
                if page_token:
                    params['pageToken'] = page_token
                data = self._get('mediaItems', params)

            items = data.get('mediaItems', [])
            yield from items

            page_token = data.get('nextPageToken')
            if not page_token:
                break

    def download_media(self, media_item: dict, destination: Path) -> Path:
        """Download a media item to destination directory."""
        import requests
        base_url = media_item.get('baseUrl', '')
        filename = media_item.get('filename', 'download')
        mime_type = media_item.get('mimeType', '')

        # Append download parameters
        if 'video' in mime_type:
            download_url = f'{base_url}=dv'
        else:
            download_url = f'{base_url}=d'

        destination.mkdir(parents=True, exist_ok=True)
        file_path = destination / filename

        response = requests.get(download_url, stream=True, timeout=60)
        response.raise_for_status()

        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=65536):
                f.write(chunk)

        return file_path

    def compare_with_local(self, local_files: list[Path]) -> dict:
        """Compare cloud items with local files by filename."""
        local_names = {f.name for f in local_files}
        cloud_items = list(self.list_media_items())
        cloud_names = {item.get('filename', '') for item in cloud_items}

        return {
            'only_local': [f for f in local_files if f.name not in cloud_names],
            'only_cloud': [i for i in cloud_items if i.get('filename', '') not in local_names],
            'both': [f for f in local_files if f.name in cloud_names],
        }

    def get_storage_quota(self) -> dict:
        """Get Google account storage quota."""
        try:
            import requests
            resp = self._session.get('https://www.googleapis.com/drive/v3/about?fields=storageQuota')
            resp.raise_for_status()
            quota = resp.json().get('storageQuota', {})
            total = int(quota.get('limit', 0))
            used = int(quota.get('usage', 0))
            return {
                'total': total,
                'used': used,
                'free': total - used,
                'percentage': round(used / total * 100, 1) if total > 0 else 0,
            }
        except Exception:
            return {'total': 0, 'used': 0, 'free': 0, 'percentage': 0}
