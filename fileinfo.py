#!/usr/bin/env python3
# encoding: utf-8

import common
import hashlib
import os

class FileInfo:

    def __init__(self, path, root_path):
        self.uid = self.gid = self.perm = self.slink= self.sha1 = self.old_sha1 = self.selabel = ""
        # 文件绝对路径
        self.path = path
        # 文件相对于"/"的路径
        if root_path in self.path:
            self.rela_path = self.path.replace(root_path, "", 1).replace("\\","/")
        else:
            self.rela_path = ""

        self.filename = os.path.split(path)[1]
        if not common.is_win():
            self.set_info(self.get_stat(self.path))

    def __eq__(self, obj):
        return all((self.sha1 == obj.sha1,
                    self.uid == obj.uid,
                    self.gid == obj.gid,
                    self.perm == obj.perm,
                    self.slink == obj.slink,
                    self.selabel == obj.selabel))

    def __hash__(self):
        return hash(self.rela_path)

    def __len__(self):
        return os.stat(self.path).st_size

    def set_info(self, info_list):
        self.uid, self.gid, self.perm, self.slink = info_list

    def calc_sha1(self):
        # 计算文件sha1
        if not os.path.isdir(self.path) and self.slink == '' :
            if not os.access(self.path, os.R_OK):
                os.system("sudo chmod +r %s" % self.path)
            with open(self.path, "rb") as f:
                self.sha1 = hashlib.sha1(f.read()).hexdigest()
        else:
            self.sha1 = 'isdirorsym'
        return self.sha1

    @staticmethod
    def get_stat(path):
        # 获取文件uid gid 权限 symlink信息 返回一个四元元组
        # 仅用于Linux环境
        fs = os.stat(path, follow_symlinks=False)
        if os.path.islink(path):
            slink = os.readlink(path)
        else:
            slink = ""
        return (fs.st_uid, fs.st_gid, oct(fs.st_mode)[-3:], slink)
