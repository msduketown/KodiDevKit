# -*- coding: utf8 -*-

# Copyright (C) 2015 - Philipp Temminghoff <phil65@kodi.tv>
# This program is Free Software see LICENSE file for details

"""
KodiDevKit is a plugin to assist with Kodi skinning / scripting using Sublime Text 3
"""


import os
import json
import colorsys
import codecs
import zipfile
import subprocess
import re
import platform
import requests
import threading
from functools import wraps
import time
import logging
import string
from lxml import etree as ET

from .polib import polib
from . import yattag

PARSER = ET.XMLParser(remove_blank_text=True, remove_comments=True)


def is_kodi_hex(text):
    """
    returns True if text is kodi-style hex value
    """
    return len(text) == 8 and all(c in string.hexdigits for c in text)


def is_number(text):
    """
    returns True if *text is a number
    """
    try:
        float(text)
        return True
    except ValueError:
        return False


def save_xml(filename, root):
    """
    save xml node *root as file with path *filename
    """
    tree = ET.ElementTree(root)
    content = ET.tostring(tree, encoding='UTF-8', xml_declaration=True)
    content = yattag.indent(string=content.decode("utf-8"),
                            indentation="\t")
    with open(filename, 'w', encoding="utf-8") as xml_file:
        xml_file.write(content)


def retry(ExceptionToCheck, tries=4, delay=3, backoff=2):
    """
    Decorator which re-tries the function in case of Exception
    """
    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except ExceptionToCheck as e:
                    msg = "%s, Retrying in %d seconds..." % (e, mdelay)
                    logging.info(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)

        return f_retry

    return deco_retry


def run_async(func):
    """
    Decorator to put a function into a separate thread
    """
    @wraps(func)
    def async_func(*args, **kwargs):
        func_hl = threading.Thread(target=func, args=args, kwargs=kwargs)
        func_hl.start()
        return func_hl

    return async_func


def check_busy(func):
    """
    Decorator to check for self.is_busy
    Only one of the decorated functions may run simultaniously
    """

    @wraps(func)
    def decorator(self, *args, **kwargs):
        if self.is_busy:
            logging.critical("Already busy. Please wait.")
            return None
        self.is_busy = True
        try:
            func(self, *args, **kwargs)
        except Exception as e:
            logging.critical(e)
        self.is_busy = False
    return decorator


def get_sublime_path():
    """
    get cmd call for different platforms to execute Sublime Text
    """
    if platform.system() in ['Darwin', 'Linux']:
        return "subl"
    elif os.path.exists(os.path.join(os.getcwd(), "sublime_text.exe")):
        return os.path.join(os.getcwd(), "sublime_text.exe")


def get_absolute_file_paths(directory):
    """
    Generate absolute file paths for the given directory
    """
    for dirpath, _, filenames in os.walk(directory):
        for filename in filenames:
            yield os.path.abspath(os.path.join(dirpath, filename))


def make_archive(folderpath, archive):
    """
    Create zip with path *archive from folder with path *folderpath
    """
    file_list = get_absolute_file_paths(folderpath)
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for addon_file in file_list:
            path_list = re.split(r'[\\/]', addon_file)
            rel_path = os.path.relpath(addon_file, folderpath)
            if ".git" in path_list:
                continue
            if rel_path.startswith("media") and not rel_path.endswith(".xbt"):
                continue
            if rel_path.startswith("themes"):
                continue
            if addon_file.endswith(('.pyc', '.pyo', '.zip')):
                continue
            if addon_file.startswith(('.')):
                continue
            zip_file.write(addon_file, rel_path)
            logging.warning("zipped %s" % rel_path)


def to_hex(red, green, blue, alpha=None):
    """
    return rgba hex values for ST tooltip
    """
    return "#%02X%02X%02X%02X" % (red, green, blue, alpha if alpha else 255)


def get_contrast_color(col):
    """
    gets contrast color for *col (used to ensure readability)
    """
    (hue, l, saturation) = colorsys.rgb_to_hls(int(col[1:3], 16) / 255.0,
                                               int(col[3:5], 16) / 255.0,
                                               int(col[5:7], 16) / 255.0)
    lightness = 1 - l
    if abs(lightness - l) < .15:
        lightness = .15
    (red, green, blue) = colorsys.hls_to_rgb(hue, lightness, saturation)
    return to_hex(int(red * 255), int(green * 255), int(blue * 255))  # true complementary


def check_bom(filepath):
    """
    check file *filepath for BOM, return True / False
    """
    file_bytes = min(32, os.path.getsize(filepath))
    with open(filepath, 'rb') as f:
        raw = f.read(file_bytes)
    return raw.startswith(codecs.BOM_UTF8)


def check_paths(paths):
    """
    Return first valid path of *paths list
    """
    for path in paths:
        if os.path.exists(path):
            return path
    return ""


def texturepacker(media_path, settings, xbt_filename="Textures.xbt"):
    """
    run TexturePacker on *media_path,
    also needs *settings for TexturePacker path
    """
    tp_path = settings.get("texturechecker_path")
    if not tp_path:
        return None
    args = ['-dupecheck',
            '-input "%s"' % media_path,
            '-output "%s"' % os.path.join(media_path, xbt_filename)]
    if platform.system() == "Linux":
        args = ['%s %s' % (tp_path, " ".join(args))]
    else:
        args.insert(0, tp_path)
    with subprocess.Popen(args, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True, shell=True) as p:
        for line in p.stdout:
            logging.warning(line)


def check_brackets(label):
    """
    check if all brackets in *label match, return True / False
    """
    stack = []
    push_chars, pop_chars = "<({[", ">)}]"
    for c in label:
        if c in push_chars:
            stack.append(c)
        elif c in pop_chars:
            if not stack:
                return False
            else:
                stack_top = stack.pop()
                balancing_bracket = push_chars[pop_chars.index(c)]
                if stack_top != balancing_bracket:
                    return False
    return not stack


def find_word(view):
    """
    return selected text or surrounding text for first selection
    """
    for region in view.sel():
        word = view.word(region) if region.begin() == region.end() else region
        return view.substr(word) if not word.empty() else ""


def get_node_content(view, flags):
    """
    return surrounding text for for first selection
    """
    for region in view.sel():
        try:
            bracket_region = view.expand_by_class(region, flags, '<>"[]')
            return view.substr(bracket_region)
        except Exception:
            return ""


def jump_to_label_declaration(view, label_id):
    """
    prints properly formatted output for json objects
    """
    view.run_command("insert", {"characters": label_id})
    view.hide_popup()


def prettyprint(string):
    """
    prints properly formatted output for json objects
    """
    logging.info(json.dumps(string, sort_keys=True, indent=4, separators=(',', ': ')))


def get_po_file(po_file_path):
    """
    return pofile object, go-to-failure in case of exception
    """
    try:
        logging.info("Parsing po file %s" % po_file_path)
        return polib.pofile(po_file_path)
    except Exception as e:
        logging.warning("Error in %s:\n %s" % (po_file_path, e))
        return None


def get_root_from_file(xml_file):
    """
    return XML root node from file *filename
    """
    if not xml_file.endswith(".xml"):
        logging.info("Tried to get root from non-xml file: %s" % xml_file)
        return None
    if not os.path.exists(xml_file):
        return None
    try:
        return ET.parse(xml_file, PARSER).getroot()
    except Exception as e:
        logging.warning("Error in %s:\n %s" % (xml_file, e))
        return None


def create_new_po_file(path=None):
    """
    creates a new pofile and returns it (doesnt save yet)
    """
    po_file = polib.POFile(fpath=path)
    mail = ""
    actual_date = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    po_file.metadata = {
        'Project-Id-Version': '1.0',
        'Report-Msgid-Bugs-To': '%s' % mail,
        'POT-Creation-Date': actual_date,
        'PO-Revision-Date': actual_date,
        'Last-Translator': 'you <%s>' % mail,
        'Language-Team': 'English <%s>' % mail,
        'MIME-Version': '1.0',
        'Content-Type': 'text/plain; charset=utf-8',
        'Content-Transfer-Encoding': '8bit',
    }
    return po_file


def convert_xml_to_po(path):
    """
    convert language xmls inside *path to .po files
    """
    po_file = create_new_po_file(path)
    root = get_root_from_file(path)
    for item in root.find("string"):
        entry = polib.POEntry(msgid=item.text,
                              msgstr="",
                              msgctxt="#%s" % item.attrib["id"])
        po_file.append(entry)
    po_file.save()
    return po_file


def get_addons(reponame):
    """
    get available addons from the kodi addon repository
    """
    repo_list = 'http://mirrors.kodi.tv/addons/%s/addons.xml'
    logging.info("Downloading %s addon list" % reponame)
    r = requests.get(repo_list % reponame, stream=True)
    r.raw.decode_content = True
    root = ET.parse(r.raw)
    addons = {item.get('id'): item.get('version') for item in root.iter('addon')}
    return addons
