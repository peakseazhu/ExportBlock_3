from numcodecs import Blosc


def build_compressor(name: str) -> Blosc:
    cname = name or "zstd"
    return Blosc(cname=cname, clevel=3, shuffle=Blosc.BITSHUFFLE)
