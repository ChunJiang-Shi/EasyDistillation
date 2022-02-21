from io import SEEK_CUR, BufferedReader
from math import prod
import re
import struct
from time import time
from typing import Dict, Tuple
import xml.etree.ElementTree as ET

from .abstract import ElementMetaData, FileData, File
from .backend import getBackend


class IldgFileData(FileData):
    def __init__(self, file: str, elem: ElementMetaData, offset: Tuple[int], xmlTree: ET.ElementTree) -> None:
        self.file = file
        self.offset = offset[0]
        tag = re.match(r"\{.*\}", xmlTree.getroot().tag).group(0)
        # lattSize = [
        #     int(xmlTree.find(f"{tag}lx").text),
        #     int(xmlTree.find(f"{tag}ly").text),
        #     int(xmlTree.find(f"{tag}lz").text),
        #     int(xmlTree.find(f"{tag}lt").text),
        # ]
        self.shape = elem.shape
        self.stride = [prod(self.shape[i:]) for i in range(1, len(self.shape))] + [1]
        self.dtype = elem.dtype
        self.bytes = int(re.match(r"^[<>=]?[iufc](?P<bytes>\d+)$", elem.dtype).group("bytes"))
        assert self.bytes == int(xmlTree.find(f"{tag}precision").text) // 8 * 2
        assert prod(elem.shape) * self.bytes == offset[1]
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
        if isinstance(key, int):
            key = (key,)
        s = time()
        ret = numpy.fromfile(
            self.file,
            dtype=self.dtype,
            count=self.getCount(key),
            offset=self.offset + self.getOffset(key),
        ).reshape(self.shape[len(key) :])
        self.timeInSec += time() - s
        self.sizeInByte += ret.nbytes
        return ret


class IldgFile(File):
    def __init__(self) -> None:
        self.magic: str = b"\x45\x67\x89\xAB\x00\x01"
        self.file: str = None
        self.data: IldgFileData = None

    def readMetaData(self, f: BufferedReader):
        objPosSize: Dict[str, Tuple[int]] = {}
        buffer = f.read(8)
        while buffer != b"":
            assert buffer.startswith(b"\x45\x67\x89\xAB\x00\x01")
            length = (struct.unpack(">Q", f.read(8))[0] + 7) // 8 * 8
            header = f.read(128).strip(b"\x00").decode("utf-8")
            objPosSize[header] = (f.tell(), length)
            f.seek(length, SEEK_CUR)
            buffer = f.read(8)

        offset = objPosSize["ildg-binary-data"]
        f.seek(objPosSize["ildg-format"][0])
        xmlTree = ET.ElementTree(ET.fromstring(f.read(objPosSize["ildg-format"][1]).strip(b"\x00").decode("utf-8")))
        return offset, xmlTree

    def getFileData(self, key: str, elem: ElementMetaData) -> FileData:
        if self.file != key:
            self.file = key
            with open(key, "rb") as f:
                offset, xmlTree = self.readMetaData(f)
            self.data = IldgFileData(key, elem, offset, xmlTree)
        return self.data


class GaugeField(IldgFile):
    def __init__(self, directory: str) -> None:
        super().__init__()
        self.id = "su3gauge"
        self.prefix = f"{directory}/"
        self.suffix = ".lime"

    def __getitem__(self, key: str):
        elem = ElementMetaData([128, 16 ** 3, 4, 3, 3], ">c16", 0)
        return super().getFileData(f"{self.prefix}{key}{self.suffix}", elem)