#!/usr/bin/env python3
# encoding: utf-8

import os
import re
import shutil
import sys
import tempfile
import zipfile

from bootimg import unpack_bootimg
from collections import OrderedDict
from sdat2img import main as _sdat2img

class PathNotFoundError(OSError):
    pass

def is_win():
    return os.name == "nt"

def get_bin(program_name):
    return os.path.join(os.getcwd(), "bin", program_name)

def check_file(file_path):
    if not os.path.exists(file_path):
        raise PathNotFoundError("%s: No such file or directory" %file_path)

def mkdir(path):
    # 创建目录
    if os.path.exists(path):
        if not os.path.isdir(path):
            try:
                os.remove(path)
            except:
                pass
        else:
            return
    os.makedirs(path)

def remove_path(path):
    # 移除文件/目录(如果存在的话)
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.exists(path):
        os.remove(path)

def file2file(src, dst, move=False):
    # 复制文件到文件
    # move为True时移动文件而不是复制文件
    mkdir(os.path.split(dst)[0])
    if move:
        shutil.move(src, dst)
    else:
        shutil.copyfile(src, dst)
    return dst

def dir2dir(src, dst):
    # 复制文件夹到文件夹
    mkdir(os.path.split(dst)[0])
    shutil.copytree(src, dst)
    return dst

def extract_zip(file_path):
    # 解压zip文件
    check_file(file_path)
    extract_path = tempfile.mkdtemp("", "OTA-maker_")
    with zipfile.ZipFile(file_path, "r") as zip:
        zip.extractall(extract_path)
    return extract_path

def extract_brotli(file_path):
    # 解压 *.br 压缩文件
    check_file(file_path)
    extract_path = file_path[:-3]
    if is_win:
        brotli_bin = "brotli.exe"
    else:
        brotli_bin = "brotli" 
    os.system(" ".join((
        get_bin(brotli_bin), "-d", file_path, "-o", extract_path
    )))
    if not os.path.exists(extract_path):
        raise Exception("%s: Failed to extract this file!" % file_path)
    return extract_path

def extract_sdat(file_path):
    # 解包 *.new.dat 文件
    check_file(file_path)
    OUTPUT_IMAGE_FILE = file_path[:-8] + ".img"
    TRANSFER_LIST_FILE = file_path[:-8] + ".transfer.list"
    _sdat2img(TRANSFER_LIST_FILE, file_path, OUTPUT_IMAGE_FILE,
              silent_mode=True)
    return OUTPUT_IMAGE_FILE

def extract_img(file_path):
    check_file(file_path)
    out_path=file_path[:-4]
    mkdir(out_path)
    if is_win():
        # 使用 imgextractor.exe 提取 *.img
        exit_code = os.system(" ".join((
            get_bin("imgextractor.exe"), file_path, out_path, "> NUL"
        )))
        if exit_code != 0:
            raise Exception("Failed to extract %s with imgextractor.exe!" %file_path)
    else:
        # 挂载 *.img 
        print("Mounting ext4 image...")
        exit_code = os.system(" ".join((
            "sudo", "mount", file_path, out_path, "-o", "loop,rw", "-t", "ext4"
        )))
        if exit_code != 0:
            raise Exception("Failed to mount %s" %file_path)
    return out_path

def extract_bootimg(file_path):
    # 解包boot.img文件
    check_file(file_path)
    bimg_path = os.path.split(file_path)[0] + '/bootimg_extract'
    mkdir(bimg_path)
    out_dir = bimg_path + '/ramdisk'
    workdir_bak = os.getcwd()
    os.chdir(bimg_path)
    unpack_bootimg(file_path, directory = out_dir)
    os.chdir(workdir_bak)
    return out_dir

def make_zip(path, zip_path):
    # 打包zip文件
    # 打包目录下的所有文件和目录 而并非打包目录本身
    if not os.path.isdir(path):
        raise PathNotFoundError("%s: No such directory" %path)
    if os.path.exists(zip_path):
        remove_path(zip_path)
    with zipfile.ZipFile(zip_path, "w") as zip:
        for root, dirs, files in os.walk(path, topdown=True):
            for f in files:
                f_fullpath = os.path.join(root, f)
                # diff文件不再压缩(因为已经被gz压缩过了)
                if f.endswith(".p"):
                    zip.write(f_fullpath,
                              arcname=f_fullpath.replace(path, "", 1),
                              compress_type=zipfile.ZIP_STORED)
                else:
                    zip.write(f_fullpath,
                              arcname=f_fullpath.replace(path, "", 1),
                              compress_type=zipfile.ZIP_DEFLATED)
    return zip_path

def read_statfile(path, def_sys_root = '/system'):
    # 解析由Imgextractor.exe解包*.img时生成的*_statfile.txt文件
    # 生成文件和目录的信息字典
    # 仅用于Windows环境
    save_dic = {}
    openfile = path + "_statfile.txt"
    check_file(openfile)
    with open(openfile, "r", encoding="UTF-8", errors="ignore") as f:
        for line in f.readlines():
            try:
                info = list(line.strip()[line.index("/") + 1:].split())
            except:
                continue
            if len(info) == 4:
                info.append("")
            save_dic[os.path.join(def_sys_root, *info[0].split("/")[1:]).replace('\\', '/')] = info[1:]
            # info 列表各元素信息:
            # 文件相对路径 uid gid 权限 符号链接(没有则为"")
            # 最终返回的字典 以文件相对路径为key 其他信息的列表为value
    return save_dic

def get_file_contexts(file_path, t_root=''):
    # 解析file_contexts文件 生成属性键值字典
    check_file(file_path)
    # 如果是*.bin文件则先进行转换
    if os.path.basename(file_path).endswith(".bin"):
        fpath = file_path[:-4]
        if is_win():
            os.system(" ".join((
                get_bin("sefcontext_decompile.exe"), "-o", fpath, file_path
            )))
        else:
            os.system(" ".join((
                get_bin("sefcontext_decompile"), "-o", fpath, file_path
            )))
    else:
        fpath = file_path
    sel_dic = OrderedDict()
    with open(fpath, "r", encoding="UTF-8", errors="ignore") as f:
        for line in f.readlines():
            linesp = line.strip()
            if not linesp or linesp.startswith("#"): continue
            k, v = linesp.split(maxsplit=1)
            if v.startswith("--"):
                v = v.split(maxsplit=1)[-1].strip()
            sel_dic[re.compile(k)] = v
            if t_root: sel_dic[re.compile(t_root + k)] = v
    return sel_dic


def get_selabel_linux(path):
    # 获取path的SE上下文属性
    # 仅用于Linux环境
    if os.path.isdir(path):
        path, name = os.path.split(path)
        with os.popen("ls -Z %s > /dev/null" % path) as infos:
            for s in infos.readlines():
                info = s.strip().split()
                if name in info:
                    break
    else:
        with os.popen("ls -Z %s" % path) as infos:
            info = infos.read().strip().split()
    if len(info) > 2:
        return info[3]
    else:
        return info[0]

def get_selabel_windows(dic, key_set, path):
    # 通过检索get_file_contexts函数返回的dic
    # 获取path的SE上下文属性 返回最符合的结果
    k = ""
    old_length = 0
    for reg in key_set:
        tmp_matched = reg.match(path)
        if tmp_matched:
            mat_length = tmp_matched.span()[1]
            if mat_length > old_length:
                k = dic[reg]
                old_length = mat_length
    if not k:
        print("WARNING: Couldn't find %s's selabel" %path)
    return k

def get_build_prop(file_path):
    # 解析build.prop文件 生成属性键值字典
    check_file(file_path)
    prop_dic = {}
    with open(file_path, "r", encoding="UTF-8", errors="ignore") as f:
        for line in f.readlines():
            linesp = line.strip()
            if not linesp:
                continue
            if linesp.startswith("#"):
                continue
            if "=" in line:
                k, _, v = linesp.partition("=")
                prop_dic[k] = v
    return prop_dic

def parameter_split(line):
    # 对edify脚本的参数进行拆分
    # 拆分得到的列表的第一个元素为函数名
    start = line.index("(")
    end = line.rindex(")")
    pars = []
    pars.append(line[:start])
    for par in line[start+1:end].split(", "):
        if par.startswith("\""):
            # 有时候得到的字符串会加上引号
            # 所以在这里把它去掉 虽然看起来没什么必要
            par = par[1:-1]
        pars.append(par)
    return pars
