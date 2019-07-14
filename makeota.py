#!/usr/bin/env python3
# encoding: utf-8

import os
import sys
import bsdiff4
import hashlib
import tempfile
from common import *
from multiprocessing import Pool
from fileinfo import FileInfo
from updater import Updater

__version__ = "1.0.5"

# 执行 bsdiff 使用的进程数
BSDIFF_PROC_NUM = 4

def main(OLD_ZIP, NEW_ZIP, OUT_PATH):
    print('Unpacking %s ...' %OLD_ZIP)
    OLD_ZIP_PATH = extract_zip(OLD_ZIP)
    print('Unpacking %s ...' %NEW_ZIP)
    NEW_ZIP_PATH = extract_zip(NEW_ZIP)

    HAS_IMG = True
    IS_TREBLE = False

    if not os.path.exists(NEW_ZIP_PATH + '/system/app'):
        print('Extracting *.br and *.new.dat ...')
        unpack_to_img(OLD_ZIP_PATH)
        unpack_to_img(NEW_ZIP_PATH)
        print('Extracting system partition EXT4 Image...')
        extract_img(NEW_ZIP_PATH + '/system.img')
        if not os.path.exists(OLD_ZIP_PATH + '/system/app'):
            extract_img(OLD_ZIP_PATH + '/system.img')
    else:
        HAS_IMG = False

    if os.path.exists(NEW_ZIP_PATH + '/vendor.img'):
        print('Found Project-Treble supported device')
        IS_TREBLE = True
        print('Extracting vendor partition EXT4 Image...')
        extract_img(NEW_ZIP_PATH + '/vendor.img')
        if os.path.exists(OLD_ZIP_PATH + '/vendor.img'):
            extract_img(OLD_ZIP_PATH + '/vendor.img')

    # 检查 system-as-root 设备
    if os.path.exists(NEW_ZIP_PATH + '/system/default.prop'):
        IS_SYS_AS_ROOT = True
        print('Found system-as-root device')
        if not is_win():
            print('Found system-as-root device, remounting system partition')
            mkdir(NEW_ZIP_PATH + '/system_root')
            os.system(" ".join(('sudo', 'umount', OLD_ZIP_PATH + '/system')))
            os.system(" ".join(('sudo', 'umount', NEW_ZIP_PATH + '/system')))
            os.system(" ".join(('sudo', 'mount',
                    OLD_ZIP_PATH + '/system.img',
                    OLD_ZIP_PATH + '/system_root',
                    '-o', 'rw,loop')))
            os.system(" ".join(('sudo', 'mount',
                    OLD_ZIP_PATH + '/system.img',
                    OLD_ZIP_PATH + '/system_root',
                    '-o', 'rw,loop')))
        else:
            os.rename(OLD_ZIP_PATH + '/system', OLD_ZIP_PATH + '/system_root')
            os.rename(OLD_ZIP_PATH + '/system_statfile.txt', OLD_ZIP_PATH + '/system_root_statfile.txt')
            os.rename(NEW_ZIP_PATH + '/system', NEW_ZIP_PATH + '/system_root')
            os.rename(NEW_ZIP_PATH + '/system_statfile.txt', NEW_ZIP_PATH + '/system_root_statfile.txt')
        SYSTEM_ROOT = "/system_root"
    else:
        IS_SYS_AS_ROOT = False
        SYSTEM_ROOT = '/system'

    # 读取 ROM 中的 build.prop
    print("Getting ROM information...")
    if not IS_SYS_AS_ROOT:
        build_prop_dict = get_build_prop(NEW_ZIP_PATH + SYSTEM_ROOT + '/build.prop')
    else:
        build_prop_dict = get_build_prop(NEW_ZIP_PATH + SYSTEM_ROOT + '/system/build.prop')
    print('------ ROM Info -------')
    print('Device: %s' %build_prop_dict.get('ro.product.device'))
    print('Android Version: %s' %build_prop_dict.get('ro.build.version.release'))
    print('API level: %s' %build_prop_dict.get('ro.build.version.sdk'))
    print('Fingerprint: %s' %build_prop_dict.get('ro.build.fingerprint'))
    print('')

    # 取得文件列表并存储为集合
    print('Comparing system partition...')
    # 如果是Windows, 取 statfile.txt 作为字典，在get_fileinfo_set中传入
    if HAS_IMG and is_win():
        system_dict = read_statfile(NEW_ZIP_PATH + SYSTEM_ROOT, def_sys_root=SYSTEM_ROOT)
    else:
        system_dict = {}
    old_system_set = get_fileinfo_set(OLD_ZIP_PATH, OLD_ZIP_PATH + SYSTEM_ROOT, system_dict)
    new_system_set = get_fileinfo_set(NEW_ZIP_PATH, NEW_ZIP_PATH + SYSTEM_ROOT, system_dict)
    # 去除相同的文件
    diff_set = old_system_set.symmetric_difference(new_system_set)
    if IS_TREBLE:
        print('Comparing vendor partition...')
        if HAS_IMG and is_win():
            vendor_dict = read_statfile(NEW_ZIP_PATH + '/vendor', def_sys_root='/vendor')
        else:
            vendor_dict = {}
        old_vendor_set = get_fileinfo_set(OLD_ZIP_PATH, OLD_ZIP_PATH + '/vendor/', vendor_dict)
        new_vendor_set = get_fileinfo_set(NEW_ZIP_PATH, NEW_ZIP_PATH + '/vendor/', vendor_dict)
        diff_set = diff_set | old_vendor_set.symmetric_difference(new_vendor_set)

    OTA_ZIP_PATH = tempfile.mkdtemp("", "OTA-maker_")

    print('Reading the difference file list...')
    print('Copying files and generating patches...')
    patch_set = set(); rem_set = set(); sym_set = set(); new_set = set()
    old_sha1_dict = {}
    tp_executor = Pool(processes=BSDIFF_PROC_NUM)
    for tmp_item in diff_set:
        if OLD_ZIP_PATH in tmp_item.path:
            if not os.path.exists(NEW_ZIP_PATH + tmp_item.rela_path):
                rem_set.add(tmp_item)
            else:
                old_sha1_dict[tmp_item.rela_path] = tmp_item.sha1
        else:
            if tmp_item.slink:
                sym_set.add(tmp_item)
                rem_set.add(tmp_item)
            elif not os.path.exists(OLD_ZIP_PATH + tmp_item.rela_path):
                new_file_path = OTA_ZIP_PATH + tmp_item.rela_path
                if not os.path.isdir(NEW_ZIP_PATH + tmp_item.rela_path):
                    mkdir(os.path.split(new_file_path)[0])
                    file2file(NEW_ZIP_PATH + tmp_item.rela_path, new_file_path)
                new_set.add(tmp_item)
            else:
                patch_set.add(tmp_item)
                ota_patch_path = OTA_ZIP_PATH + '/patch' + tmp_item.rela_path + '.p'
                mkdir(os.path.split(ota_patch_path)[0])
                tp_executor.apply_async(bsdiff4.file_diff, 
                                    (OLD_ZIP_PATH + tmp_item.rela_path,
                                     NEW_ZIP_PATH + tmp_item.rela_path,
                                     ota_patch_path))
    tp_executor.close()
    tp_executor.join()

    print('Reading SELinux context...')
    if not is_win() and HAS_IMG:
        for tmp_item in new_set:
            tmp_item.selabel = get_selabel_linux(tmp_item.path)
    else:
        if IS_SYS_AS_ROOT: 
            tmp_root = SYSTEM_ROOT
        else:
            tmp_root = ''
        if os.path.exists(NEW_ZIP_PATH + SYSTEM_ROOT + '/etc/selinux/plat_file_contexts'):
            tmp_file_context = get_file_contexts(NEW_ZIP_PATH + SYSTEM_ROOT + '/etc/selinux/plat_file_contexts', tmp_root)
        elif os.path.exists(NEW_ZIP_PATH + SYSTEM_ROOT + '/system/etc/selinux/plat_file_contexts'):
            tmp_file_context = get_file_contexts(NEW_ZIP_PATH + SYSTEM_ROOT + '/system/etc/selinux/plat_file_contexts', tmp_root)
        else:
            boot_out = extract_bootimg(NEW_ZIP_PATH + '/boot.img')
            if os.path.exists(boot_out + '/file_contexts'):
                tmp_file_context = get_file_contexts(boot_out + '/file_contexts')
            elif os.path.exists(boot_out + '/file_contexts.bin'):
                tmp_file_context = get_file_contexts(boot_out + '/file_contexts.bin')
            else:
                tmp_file_context = {}
        if os.path.exists(NEW_ZIP_PATH + '/vendor/etc/selinux/vendor_file_contexts'):
            tmp_file_context.update(get_file_contexts(NEW_ZIP_PATH + '/vendor/etc/selinux/vendor_file_contexts'))
        if os.path.exists(NEW_ZIP_PATH + '/vendor/etc/selinux/nonplat_file_contexts'):
            tmp_file_context.update(get_file_contexts(NEW_ZIP_PATH + '/vendor/etc/selinux/nonplat_file_contexts'))
        tmp_keys = tmp_file_context.keys()
        for tmp_item in new_set:
            tmp_item.selabel = get_selabel_windows(tmp_file_context, tmp_keys, tmp_item.rela_path)

    print('Generating updater...')
    tmp_updater = Updater()
    mkdir(OTA_ZIP_PATH + '/install')
    if '64' in build_prop_dict.get('ro.product.cpu.abi'):
        tmp_updater.add("SYS_LD_LIBRARY_PATH=/system/lib64")
        file2file(get_bin('applypatch_64'), OTA_ZIP_PATH + '/install/applypatch')
    else:
        tmp_updater.add("SYS_LD_LIBRARY_PATH=/system/lib")
        file2file(get_bin('applypatch'), OTA_ZIP_PATH + '/install/applypatch')
    tmp_updater.check_device(
        build_prop_dict.get('ro.product.device'),
        build_prop_dict.get('ro.build.product'))
    tmp_updater.blank_line()

    tmp_updater.ui_print('This OTA package is made by OTA-maker')
    tmp_updater.ui_print('Mounting ' + SYSTEM_ROOT)
    tmp_updater.mount(SYSTEM_ROOT)
    if IS_TREBLE:
        tmp_updater.ui_print('Mounting /vendor')
        tmp_updater.mount('/vendor')

    # patch文件
    tmp_updater.ui_print('Checking files...')
    patch_list = list(patch_set)
    patch_list.sort(key=lambda x: x.rela_path)
    for tmp_item in patch_list:
        tmp_updater.apply_patch_check(tmp_item.rela_path, old_sha1_dict[tmp_item.rela_path])
    tmp_updater.blank_line()
    tmp_updater.ui_print('Extracting patch files...')
    tmp_updater.package_extract_dir('patch', '/tmp/patch')
    tmp_updater.ui_print('Patching files...')
    for tmp_item in patch_list:
        ota_patch_path = OTA_ZIP_PATH + '/patch' + tmp_item.rela_path + '.p'
        tmp_updater.apply_patch(tmp_item.rela_path, tmp_item.sha1, len(tmp_item), 
            old_sha1_dict[tmp_item.rela_path], '/tmp/patch' + tmp_item.rela_path + '.p')
    tmp_updater.blank_line()

    # 解包文件
    tmp_updater.ui_print('Extracting files...')
    tmp_updater.package_extract_dir(SYSTEM_ROOT[1:], SYSTEM_ROOT)
    if IS_TREBLE:
        tmp_updater.package_extract_dir('vendor', '/vendor')
    tmp_updater.blank_line()

    # 设置metadata
    tmp_updater.ui_print('Setting metadata...')
    new_list = list(new_set)
    new_list.sort(key=lambda x: x.rela_path)
    for tmp_item in new_list:
        tmp_updater.set_metadata(tmp_item.rela_path, tmp_item.uid, tmp_item.gid, tmp_item.perm, selabel=tmp_item.selabel)
    tmp_updater.blank_line()

    # 移除文件
    tmp_updater.ui_print('Deleting files...')
    rem_list = list(rem_set)
    rem_list.sort(key=lambda x: x.rela_path)
    for tmp_item in rem_list:
        tmp_updater.delete(tmp_item.rela_path)
    tmp_updater.blank_line()

    # 生成symlink
    tmp_updater.ui_print('Making symlinks...')
    sym_list = list(sym_set)
    sym_list.sort(key=lambda x: x.rela_path)
    for tmp_item in sym_list:
        tmp_updater.symlink(tmp_item.rela_path, tmp_item.slink)
    tmp_updater.blank_line()

    # 从原版的updater-script取得操作
    tmp_updater.add('ALLOW_ABORT = false')
    tmp_updater.ui_print('Running updater-script from source zip...')
    with open(NEW_ZIP_PATH + '/META-INF/com/google/android/updater-script', "r", encoding="UTF-8") as f:
        for line in f.readlines():
            try:
                tmp_line = parameter_split(line.strip())
                us_action = tmp_line[0]
                if us_action == "package_extract_dir":
                    if tmp_line[1] == "system" or tmp_line[1] == "vendor": continue
                    mkdir(os.path.dirname(OTA_ZIP_PATH + '/' + tmp_line[1]))
                    dir2dir(NEW_ZIP_PATH + '/' + tmp_line[1], OTA_ZIP_PATH + '/' + tmp_line[1])
                    tmp_updater.package_extract_dir(tmp_line[1], tmp_line[2])
                elif us_action == "package_extract_file":
                    mkdir(os.path.dirname(OTA_ZIP_PATH + '/' + tmp_line[1]))
                    file2file(NEW_ZIP_PATH  + '/' + tmp_line[1], OTA_ZIP_PATH  + '/' + tmp_line[1])
                    tmp_updater.package_extract_file(tmp_line[1], tmp_line[2])
                elif us_action == "ui_print":
                    tmp_updater.ui_print(" ".join(str(s) for s in tmp_line[1:]))
                elif us_action == "set_perm":
                    tmp_updater.set_perm(tmp_line[1], tmp_line[2], tmp_line[3], tmp_line[4:])
                elif us_action == "set_perm_recursive":
                    tmp_updater.set_perm_recursive(tmp_line[1], tmp_line[2], tmp_line[3], tmp_line[4], tutle(tmp_line[5:]))
                elif us_action == "set_metadata":
                    tmp_updater.set_metadata(tmp_line[1], tmp_line[3], tmp_line[5], tmp_line[7])
                elif us_action == "set_metadata_recursive":
                    tmp_updater.set_metadata_recursive(tmp_line[1], tmp_line[3], tmp_line[5], tmp_line[7], tmp_line[9])
                elif us_action == "mount":
                    tmp_updater.mount(tmp_line[-1])
                elif us_action == "umount":
                    tmp_updater.umount(tmp_line[1])
                elif us_action == "apply_patch_check":
                    tmp_updater.apply_patch_check(tmp_line[1], tutle(tmp_line[2:]))
                elif us_action == "apply_patch":
                    tmp_updater.add("apply_patch %s:%s;" 
                                    %(" ".join(str(s) for s in tmp_line[1:5]), tmp_line[6]))
                elif us_action == "show_progress":
                    tmp_updater.add("show_progress %s %s;" %(tmp_line[1], tmp_line[6]))
                elif us_action == "set_progress":
                    tmp_updater.add("set_progress %s;" %tmp_line[1])
                else:
                    print("WARNING: failed to analyze " + line.strip())
            except:
                continue

    tmp_updater.blank_line()
    tmp_updater.add("sync")
    tmp_updater.blank_line()
    tmp_updater.ui_print('Unmounting ' + SYSTEM_ROOT)
    tmp_updater.unmount(SYSTEM_ROOT)
    if IS_TREBLE:
        tmp_updater.ui_print('Unmounting /vendor...')
        tmp_updater.unmount("/vendor")
    tmp_updater.blank_line()
    tmp_updater.delete_recursive("/cache/*")
    tmp_updater.delete_recursive("/data/dalvik-cache")
    tmp_updater.blank_line()
    tmp_updater.ui_print("Done!")

    update_script_path = os.path.join(OTA_ZIP_PATH, "META-INF", "com", "google", "android")
    mkdir(update_script_path)
    new_ub = os.path.join(update_script_path, "update-binary")
    with open(new_ub, "w", encoding="UTF-8", newline="\n") as f:
        for line in tmp_updater.script:
            f.write(line)
    new_uc = os.path.join(update_script_path, "updater-script")
    with open(new_uc, "w", encoding="UTF-8", newline="\n") as f:
        f.write("# Dummy file; update-binary is a shell script.\n")

    print('Making OTA package...')
    make_zip(OTA_ZIP_PATH, OUT_PATH)

    print('Cleaning temp files...')
    if not is_win():
        os.system(" ".join(('sudo', 'umount', OLD_ZIP_PATH + SYSTEM_ROOT)))
        os.system(" ".join(('sudo', 'umount', NEW_ZIP_PATH + SYSTEM_ROOT)))
        if IS_TREBLE:
            os.system(" ".join(('sudo', 'umount', OLD_ZIP_PATH + '/vendor')))
            os.system(" ".join(('sudo', 'umount', NEW_ZIP_PATH + '/vendor')))
    remove_path(OLD_ZIP_PATH)
    remove_path(NEW_ZIP_PATH)
    remove_path(OTA_ZIP_PATH)

    print("\nDone!")
    print("Output OTA package: %s" %OUT_PATH)

def unpack_to_img(path):
    dir_list = os.listdir(path)
    for br_file in dir_list:
        if br_file[-3:] == '.br': 
            extract_brotli(os.path.join(path, br_file))
    dir_list = os.listdir(path)
    for sdat_file in dir_list:
        if sdat_file[-8:] == '.new.dat': 
            extract_sdat(os.path.join(path, sdat_file))

def get_fileinfo_set(root, path, dict):
    tmp_set = set()
    for t_root, dirs, files in os.walk(path):
        for info_file in files + dirs:
            tmp_FI = FileInfo(t_root + '/' + info_file, root)
            if is_win():
                tmp_FI.set_info(dict.get(tmp_FI.rela_path, [0, 0, 644, '']))
            tmp_FI.calc_sha1()
            tmp_set.add(tmp_FI)
    return tmp_set

if __name__ == '__main__':
    try:
        OLD_ZIP = str(sys.argv[1])
        NEW_ZIP = str(sys.argv[2])
    except IndexError:
        print('OTA-maker ver: %s' %__version__)
        print('by cjybyjk')
        print('\nUsage:  makeota.py <OLD_ZIP> <NEW_ZIP> [OUT_PATH] \n')
        sys.exit()

    try:
        OUT_PATH = str(sys.argv[3])
    except IndexError:
        OUT_PATH = "OTA.zip"
            
    main(OLD_ZIP, NEW_ZIP, OUT_PATH)
    sys.exit(0)
