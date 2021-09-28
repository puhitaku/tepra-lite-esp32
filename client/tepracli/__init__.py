from typing import Tuple

import requests

min_width = 84
height = 64  # px


class Client:
    def __init__(self, origin):
        self.origin = origin

    def get_battery(self) -> Tuple[int, str]:
        res = requests.get(f'http://{self.origin}/battery')
        if res.status_code != 200:
            return 0, f'the server returned non-200: {res.status_code}'

        j = res.json()
        bat = j.get('battery')
        if bat is None:
            return 0, f'unexpected body: {j}'

        return bat, ''

    def post_depth(self, depth: int) -> str:
        res = requests.post(f'http://{self.origin}/depth', json={'depth': depth})
        j = res.json()
        err = j.get('error', '')
        if err:
            return f'Printer returned an error: {err}'
        return ''

    def post_print(self, compressed_image: bytes) -> str:
        res = requests.post(
            f'http://{self.origin}/prints',
            compressed_image,
            headers={'Content-Type': 'application/octet-stream'},
        )
        j = res.json()
        err = j.get('error', '')
        if err:
            return f'Printer returned an error: {err}'
        return ''
