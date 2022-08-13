import struct
import sys
import pandas as pd


# NOTE: Adapted from:
#   https://github.com/bulletphysics/bullet3/blob/master/examples/pybullet/examples/dumpLog.py

def load_df(filename, verbose=False, dump=False):
    f = open(filename, 'rb')

    print(f"Opened  '{filename}'")

    keys = f.readline().decode('utf8').rstrip('\n').split(',')
    fmt = f.readline().decode('utf8').rstrip('\n')

    # The byte number of one record
    sz = struct.calcsize(fmt)
    # The type number of one record
    ncols = len(fmt)

    columns = {}
    for i in range(ncols):
        columns[keys[i]] = []
        if verbose:
            print(f"Column: '{keys[i]}' [{fmt[i]}], {struct.calcsize(fmt[i])}")
    if verbose:
        print(f"Format: {fmt}, Size: {sz}, Columns: {ncols}")

    len_chunk = sz
    chunk_index = 0  # For book-keeping only
    while len_chunk:
        check = f.read(2)
        len_chunk = 0
        if check == b'\xaa\xbb':
            mychunk = f.read(sz)
            len_chunk = len(mychunk)
            chunks = [mychunk]

            for chunk in chunks:
                if len(chunk) == sz:
                    chunk_index += 1
                    values = struct.unpack(fmt, chunk)
                    for i in range(ncols):
                        columns[keys[i]].append(values[i])
                        if verbose and dump:
                            print(f"    {keys[i]}={values[i]}")

        elif check == b'':
            print(f"Done reading log -- Variables: {ncols} -- Records: {chunk_index}")
        else:
            print("Error, expected {b'\xaa\xbb'} but received {check}")
    df = pd.DataFrame(columns)
    return df


if __name__ == "__main__":

    fileName = "pybullet_log.bin"
    if len(sys.argv) > 1:
        fileName = sys.argv[1]

    print(f"filename={fileName}")
    load_df(fileName, verbose=True, dump=True)
