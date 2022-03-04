from math import prod
import re
from time import time
from typing import Tuple

from .abstract import ElementMetaData, FileData, File
from .backend import getBackend, getNumpy


class BinaryFileData(FileData):
    def __init__(self, file: str, elem: ElementMetaData) -> None:
        self.file = file
        self.shape = elem.shape
        self.stride = [prod(self.shape[i:]) for i in range(1, len(self.shape))] + [1]
        self.dtype = elem.dtype
        self.bytes = int(re.match(r"^[<>=]?[iufc](?P<bytes>\d+)$", elem.dtype).group("bytes"))
        self.timeInSec = 0.0
        self.sizeInByte = 0

    def getCount(self, key: Tuple[int]):
        return self.stride[len(key) - 1]

    def getOffset(self, key: Tuple[int]):
        offset = 0
        for a, b in zip(key, self.stride[0 : len(key)]):
            offset += a * b
        return offset * self.bytes

    def __getitem__(self, key: Tuple[int]):
        numpy = getBackend()
        numpy_base = getNumpy()
        if isinstance(key, int):
            key = (key,)
        s = time()
        # ret = numpy.fromfile(
        #     self.file,
        #     dtype=self.dtype,
        #     count=self.getCount(key),
        #     offset=self.getOffset(key),
        # ).reshape(self.shape[len(key) :])
        ret = numpy.asarray(
            numpy_base.memmap(
                self.file,
                dtype=self.dtype,
                mode="r",
                shape=tuple(self.shape),
            )[key]
        )
        self.timeInSec += time() - s
        self.sizeInByte += ret.nbytes
        return ret


class BinaryFile(File):
    def __init__(self) -> None:
        self.file: str = None
        self.data: BinaryFileData = None

    def getFileData(self, key: str, elem: ElementMetaData) -> FileData:
        if self.file != key:
            self.file = key
            self.data = BinaryFileData(key, elem)
        return self.data
