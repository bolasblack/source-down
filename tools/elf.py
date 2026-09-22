"""Read the linking facts of supported ELF artifacts without executing them."""
import struct


def linking(path):
    data = path.read_bytes()
    if data[:4] != b"\x7fELF":
        return None
    if data[:6] != b"\x7fELF\x02\x01" or len(data) < 64:
        raise ValueError("artifact must be a complete little-endian ELF64 executable")
    machine = struct.unpack_from("<H", data, 18)[0]
    offset = struct.unpack_from("<Q", data, 32)[0]
    size, count = struct.unpack_from("<HH", data, 54)
    if size < 56 or offset + size * count > len(data):
        raise ValueError("invalid ELF program header table")
    interpreter, needed = None, False
    for number in range(count):
        kind, _, start, _, _, length, _, _ = struct.unpack_from("<IIQQQQQQ", data, offset + number * size)
        if start + length > len(data):
            raise ValueError("ELF segment extends beyond the artifact")
        if kind == 3:  # PT_INTERP
            interpreter = data[start:start + length].rstrip(b"\0").decode()
        elif kind == 2:  # PT_DYNAMIC
            if length % 16:
                raise ValueError("invalid ELF dynamic segment")
            needed |= any(struct.unpack_from("<q", data, at)[0] == 1
                          for at in range(start, start + length, 16))
    return {"machine": machine, "interpreter": interpreter, "shared_library_dependencies": needed}
