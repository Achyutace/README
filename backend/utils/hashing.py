import hashlib

def calculate_stream_hash(stream) -> str:
    """计算文件流的 SHA256 Hash"""
    sha256 = hashlib.sha256()
    for chunk in iter(lambda: stream.read(8192), b""):
        sha256.update(chunk)
    stream.seek(0)
    return sha256.hexdigest()
