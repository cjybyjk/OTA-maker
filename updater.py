#!/usr/bin/env python3
# encoding: utf-8

import time
from common import get_bin

class Updater:

    def __init__(self):
        self.script = []
        basefile = get_bin("update-binary")
        with open(basefile, "r", encoding="UTF-8") as f:
            for line in f.readlines():
                self.script.append(line)
        self.blank_line()
        self.script.append("# The above is function definition section.\n")
        self.blank_line()
        self.script.append("#" * 80 + "\n")
        self.blank_line()
        self.script.append("# The following is the script to execute.\n")
        self.script.append("# Generate by OTA-maker (By cjybyjk)\n")
        time_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(time.time()))
        self.script.append("# Generate at: %s\n" % time_str)
        self.blank_line()
        # 添加时间戳校验，防止新版ROM刷入旧版OTA更新
        self.script.append(
            '[ $(getprop ro.build.date.utc) -lt %s ] || ' 
            'abort "Can\'t install this package (%s) over newer '
            'build ($(getprop ro.build.date))."' %(int(time.time()), time_str))
        self.blank_line()

    def check_device(self, model, *ext_models):
        s = "[ \"$(getprop ro.product.device)\" == \"%s\" ] || " % model
        s += "[ \"$(getprop ro.build.product)\" == \"%s\" ] || " % model
        for ext_m in ext_models:
            if ext_m != model:
                s += "[ \"$(getprop ro.product.device)\" == \"%s\" ] || " % ext_m
                s += "[ \"$(getprop ro.build.product)\" == \"%s\" ] || " % ext_m
        s += ("abort \"This package is for device:%s; "
              % ",".join([str(m) for m in (model, *ext_models)]))
        s += "this device is $(getprop ro.product.device).\";\n"
        self.script.append(s)

    def add(self, string, end="\n"):
        self.script.append("%s%s" % (string, end))

    def blank_line(self):
        self.script.append("\n")

    def abort(self, string, space_no=0):
        self.script.append(" " * space_no + "abort \"%s\";\n" % string)

    def ui_print(self, string, space_no=0):
        self.script.append(" " * space_no + "ui_print \"%s\";\n" % string)

    def mount(self, path):
        self.script.append("mount %s\n" % path)

    def unmount(self, path):
        self.script.append("umount %s\n" % path)

    def package_extract_file(self, s_file, d_file):
        self.script.append("package_extract_file %s %s\n" % (s_file, d_file))

    def package_extract_dir(self, s_dir, d_dir):
        self.script.append("package_extract_dir %s %s\n" % (s_dir, d_dir))

    def delete(self, *files):
        self.script.append("delete %s\n" % " ".join(files))

    def delete_recursive(self, *dirs):
        self.script.append("delete_recursive %s\n" % " ".join(dirs))

    def symlink(self, path, *links):
        self.script.append("symlink %s %s\n" % (path, " ".join(links)))

    def set_perm(self, owner, group, mode, *files):
        self.script.append("set_perm %s %s %s %s\n"
                           % (owner, group, mode, " ".join(files)))

    def set_perm_recursive(self, owner, group, dmode, fmode, *dirs):
        self.script.append("set_perm %s %s %s %s %s\n"
                           % (owner, group, dmode, fmode, " ".join(dirs)))

    def set_metadata(self, file, uid, gid, mode,
                     capabilities=None, selabel=None):
        s = "set_metadata %s uid %s gid %s mode %s" % (file, uid, gid, mode)
        if capabilities:
            s += " capabilities %s" % capabilities
        if selabel:
            s += " selabel %s" % selabel
        self.script.append(s + "\n")

    def set_metadata_recursive(self, dir, uid, gid, dmode, fmode,
                               capabilities=None, selabel=None):
        s = ("set_metadata_recursive %s uid %s gid %s dmode %s fmode %s"
             % (dir, uid, gid, dmode, fmode))
        if capabilities:
            s += " capabilities %s" % capabilities
        if selabel:
            s += " selabel %s" % selabel
        self.script.append(s + "\n")

    def apply_patch_check(self, spath, *f_shas):
        self.script.append("apply_patch_check %s %s\n" % (spath, " ".join(f_shas)))

    def apply_patch(self, spath, f_sha1, tgtsize, p_sha1, p_path):
        # applypatch <目标文件路径> <-> <打补丁后的文件哈希> \
        #            <打补丁后的文件大小> <原文件哈希:补丁文件路径>
        # 其中 - 参数暗示覆盖原文件
        self.script.append("apply_patch %s - %s %s %s:%s\n"
                           % (spath, f_sha1, tgtsize, p_sha1, p_path))
