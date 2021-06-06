class _Optional:
    def __getitem__(self, _):
        return None


Optional = _Optional()
