class _Optional:
    def __getitem__(self, _):
        return None


class _Tuple:
    def __getitem__(self, _):
        return None


Optional = _Optional()
Tuple = _Tuple()
