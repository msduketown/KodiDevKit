import os
from Utils import *
import re

DEFAULT_LANGUAGE_FOLDER = "English"


class InfoProvider():

    def __init__(self):
        self.include_list = {}
        self.include_file_list = {}
        self.window_file_list = {}
        self.color_list = []
        self.addon_xml_file = ""
        self.addon_lang_file = ""
        self.color_file = ""
        self.project_path = ""
        self.addon_type = ""
        self.addon_name = ""
        self.builtin_list = []
        self.fonts = {}
        self.string_list = []
        self.xml_folders = []
        self.addon_string_list = []
        self.settings_loaded = False

    def init_addon(self, path):
        self.addon_type = ""
        self.addon_name = ""
        self.project_path = path
        self.addon_lang_file = ""
        self.addon_xml_file = checkPaths([os.path.join(self.project_path, "addon.xml")])
        self.xml_folders = []
        self.fonts = []
        if self.addon_xml_file:
            root = get_root_from_file(self.addon_xml_file)
            for item in root.xpath("/addon[@id]"):
                self.addon_name = item.attrib["id"]
                break
            if root.find(".//import[@addon='xbmc.python']") is None:
                self.addon_type = "skin"
                for node in root.findall('.//res'):
                    self.xml_folders.append(node.attrib["folder"])
            else:
                self.addon_type = "python"
                # TODO: parse all python skin folders correctly
                paths = [os.path.join(self.project_path, "resources", "skins", "Default", "720p"),
                         os.path.join(self.project_path, "resources", "skins", "Default", "1080i")]
                folder = checkPaths(paths)
                self.xml_folders.append(folder)
        self.update_labels()
        if self.xml_folders:
            log("Kodi project detected: " + path)
            self.update_include_list()
            self.get_colors()
            self.get_fonts()
            # sublime.status_message("SublimeKodi: successfully loaded addon")

    def media_path(self):
        paths = [os.path.join(self.project_path, "media"),
                 os.path.join(self.project_path, "resources", "skins", "Default", "media")]
        return checkPaths(paths)

    def get_colors(self):
        self.color_list = []
        color_path = os.path.join(self.project_path, "colors")
        if not self.addon_xml_file or not os.path.exists(color_path):
            return False
        for path in os.listdir(color_path):
            log("found color file: " + path)
            file_path = os.path.join(color_path, path)
            root = get_root_from_file(file_path)
            for node in root.findall("color"):
                color_dict = {"name": node.attrib["name"],
                              "line": node.sourceline,
                              "content": node.text,
                              "filename": file_path}
                self.color_list.append(color_dict)
            log("color list: %i colors found" % len(self.color_list))

    def get_fonts(self):
        if not self.addon_xml_file or not self.xml_folders:
            return False
        self.fonts = {}
        for folder in self.xml_folders:
            paths = [os.path.join(self.project_path, folder, "Font.xml"),
                     os.path.join(self.project_path, folder, "font.xml")]
            font_file = checkPaths(paths)
            if font_file:
                self.fonts[folder] = []
                root = get_root_from_file(font_file)
                for node in root.find("fontset").findall("font"):
                    string_dict = {"name": node.find("name").text,
                                   "size": node.find("size").text,
                                   "line": node.sourceline,
                                   "content": ET.tostring(node, pretty_print=True),
                                   "file": font_file,
                                   "filename": node.find("filename").text}
                    self.fonts[folder].append(string_dict)

    def reload_skin_after_save(self, path):
        folder = path.split(os.sep)[-2]
        if folder in self.include_file_list:
            if path in self.include_file_list[folder]:
                self.update_include_list()
        if path.endswith("colors/defaults.xml"):
            self.get_colors()
        if path.endswith("ont.xml"):
            self.get_fonts()

    def update_include_list(self):
        self.include_list = {}
        for folder in self.xml_folders:
            xml_folder = os.path.join(self.project_path, folder)
            paths = [os.path.join(xml_folder, "Includes.xml"),
                     os.path.join(xml_folder, "includes.xml")]
            self.include_file_list[folder] = []
            self.include_list[folder] = []
            include_file = checkPaths(paths)
            self.update_includes(include_file)
            log("Include List: %i nodes found in '%s' folder." % (len(self.include_list[folder]), folder))

    def update_includes(self, xml_file):
        # recursive, walks through include files and updates include list and include file list
        if os.path.exists(xml_file):
            folder = xml_file.split(os.sep)[-2]
            log("found include file: " + xml_file)
            self.include_file_list[folder].append(xml_file)
            self.include_list[folder] += get_tags_from_file(xml_file, ["include", "variable", "constant"])
            root = get_root_from_file(xml_file)
            for node in root.findall("include"):
                if "file" in node.attrib and node.attrib["file"] != "script-skinshortcuts-includes.xml":
                    xml_file = os.path.join(self.project_path, folder, node.attrib["file"])
                    self.update_includes(xml_file)
        else:
            log("Could not find include file " + xml_file)

    def update_xml_files(self):
        # update list of all include and window xmls
        self.window_file_list = {}
        for path in self.xml_folders:
            xml_folder = os.path.join(self.project_path, path)
            self.window_file_list[path] = get_xml_file_paths(xml_folder)

    def go_to_tag(self, keyword, folder):
        # jumps to the definition of ref named keyword
        # TODO: need to add param with ref type
        if keyword:
            if keyword.isdigit():
                for node in self.string_list:
                    if node["id"] == "#" + keyword:
                        if int(keyword) >= 31000 and int(keyword) <= 33000:
                            file_path = self.addon_lang_path
                        else:
                            file_path = self.kodi_lang_path
                        return "%s:%s" % (file_path, node["line"])
            else:
                # TODO: need to check for include file attribute
                for node in self.include_list[folder]:
                    if node["name"] == keyword:
                        return "%s:%s" % (node["file"], node["line"])
                for node in self.fonts[folder]:
                    if node["name"] == keyword:
                        path = os.path.join(self.project_path, folder, "Font.xml")
                        return "%s:%s" % (path, node["line"])
                for node in self.color_list:
                    if node["name"] == keyword and node["filename"].endswith("defaults.xml"):
                        return "%s:%s" % (node["filename"], node["line"])
                log("no node with name %s found" % keyword)
        return False

    def return_node_content(self, keyword=None, return_entry="content", folder=False):
        if keyword and folder:
            if folder in self.fonts:
                for node in self.fonts[folder]:
                    if node["name"] == keyword:
                        return node[return_entry]
            if folder in self.include_list:
                for node in self.include_list[folder]:
                    if node["name"] == keyword:
                        return node[return_entry]
                # log("no node with name %s found" % keyword)

    def return_label(self, selection):
        if selection.isdigit():
            id_string = "#" + selection
            for item in self.string_list:
                if id_string == item["id"]:
                    tooltips = item["string"]
                    if self.use_native:
                        tooltips += "<br>" + item["native_string"]
                    return tooltips
        return ""

    def get_settings(self, settings):
        self.kodi_path = settings.get("kodi_path")
        log("kodi path: " + self.kodi_path)
        self.use_native = settings.get("use_native_language")
        if self.use_native:
            self.language_folder = settings.get("native_language")
            log("use native language: " + self.language_folder)
        else:
            self.language_folder = DEFAULT_LANGUAGE_FOLDER
            log("use default language: English")
        self.settings_loaded = True

    def get_builtin_label(self):
        paths = [os.path.join(self.kodi_path, "addons", "resource.language.en_gb", "resources", "strings.po"),
                 os.path.join(self.kodi_path, "language", self.language_folder, "strings.po")]
        self.kodi_lang_path = checkPaths(paths)
        if self.kodi_lang_path:
            self.builtin_list = get_label_list(self.kodi_lang_path)
            log("Builtin labels loaded. Amount: %i" % len(self.builtin_list))
        else:
            self.builtin_list = []
            log("Could not find kodi language file")
            return ""

    def update_labels(self):
        if not self.addon_xml_file:
            return False
        paths = [os.path.join(self.project_path, "resources", "language", self.language_folder, "strings.po"),
                 os.path.join(self.project_path, "language", self.language_folder, "strings.po")]
        self.addon_lang_path = checkPaths(paths)
        if self.addon_lang_path:
            self.addon_string_list = get_label_list(self.addon_lang_path)
            log("Addon Labels updated. Amount: %i" % len(self.addon_string_list))
        else:
            self.addon_string_list = []
            log("Could not find add-on language file")
        self.string_list = self.builtin_list + self.addon_string_list

    def check_variables(self):
        var_regex = "\$VAR\[(.*?)\]"
        listitems = []
        for folder in self.xml_folders:
            var_refs = []
            for xml_file in self.window_file_list[folder]:
                path = os.path.join(self.project_path, folder, xml_file)
                with open(path, encoding="utf8") as f:
                    for i, line in enumerate(f.readlines()):
                        for match in re.finditer(var_regex, line):
                            item = {"line": i + 1,
                                    "type": "variable",
                                    "file": path,
                                    "name": match.group(1).split(",")[0]}
                            var_refs.append(item)
            for ref in var_refs:
                for node in self.include_list[folder]:
                    if node["type"] == "variable" and node["name"] == ref["name"]:
                        break
                else:
                    ref["message"] = "Variable not defined: %s" % ref["name"]
                    listitems.append(ref)
            ref_list = [d['name'] for d in var_refs]
            for node in self.include_list[folder]:
                if node["type"] == "variable" and node["name"] not in ref_list:
                    node["message"] = "Unused variable: %s" % node["name"]
                    listitems.append(node)
        return listitems

    def check_includes(self):
        listitems = []
        # include check for each folder separately
        for folder in self.xml_folders:
            var_refs = []
            # get all include refs
            for xml_file in self.window_file_list[folder]:
                path = os.path.join(self.project_path, folder, xml_file)
                root = get_root_from_file(path)
                if root is None:
                    continue
                for node in root.xpath(".//include"):
                        if node.text and not node.text.startswith("skinshortcuts-"):
                            name = node.text
                            if "file" in node.attrib:
                                include_file = os.path.join(self.project_path, folder, node.attrib["file"])
                                if include_file not in self.include_file_list[folder]:
                                    self.update_includes(include_file)
                        elif node.find("./param") is not None:
                            name = node.attrib["name"]
                        else:
                            continue
                        item = {"line": node.sourceline,
                                "type": node.tag,
                                "file": path,
                                "name": name}
                        var_refs.append(item)
            # find undefined include refs
            for ref in var_refs:
                for node in self.include_list[folder]:
                    if node["type"] == "include" and node["name"] == ref["name"]:
                        break
                else:
                    ref["message"] = "Include not defined: %s" % ref["name"]
                    listitems.append(ref)
            # find unused include defs
            ref_list = [d['name'] for d in var_refs]
            for node in self.include_list[folder]:
                if node["type"] == "include" and node["name"] not in ref_list:
                    node["message"] = "Unused include: %s" % node["name"]
                    listitems.append(node)
        return listitems

    def get_font_refs(self):
        font_refs = {}
        for folder in self.xml_folders:
            font_refs[folder] = []
            for xml_file in self.window_file_list[folder]:
                path = os.path.join(self.project_path, folder, xml_file)
                font_refs[folder].extend(get_refs_from_file(path, ".//font"))
        return font_refs

    def check_fonts(self):
        listitems = []
        font_refs = self.get_font_refs()
        for folder in self.xml_folders:
            fontlist = ["-"]
            # create a list with all font names from default fontset
            for item in self.fonts[folder]:
                fontlist.append(item["name"])
            # find undefined font refs
            for ref in font_refs[folder]:
                if ref["name"] not in fontlist:
                    ref["message"] = "Font not defined: %s" % ref["name"]
                    listitems.append(ref)
            # find unused font defs
            ref_list = [d['name'] for d in font_refs[folder]]
            for node in self.fonts[folder]:
                if node["name"] not in ref_list:
                    node["message"] = "Unused font: %s" % node["name"]
                    listitems.append(node)
        return listitems

    def check_ids(self):
        window_regex = r"(?:Dialog.Close|Window.IsActive|Window.IsVisible|Window)\(([0-9]+)\)"
        control_regex = "^(?!.*IsActive)(?!.*Window.IsVisible)(?!.*Dialog.Close)(?!.*Window).*\(([0-9]*?)\)"
        builtin_window_ids = [0, 1, 2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 15, 16, 17,
                              18, 19, 20, 21, 25, 28, 29, 34, 40, 100, 101, 103,
                              104, 106, 107, 109, 111, 113, 114, 115, 120, 122, 123,
                              124, 125, 126, 128, 129, 130, 131, 132, 134, 135, 136,
                              137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147,
                              149, 150, 151, 152, 153, 500, 501, 502, 503, 615, 616,
                              617, 618, 619, 620, 621, 622, 623, 624, 602, 603, 604,
                              605, 606, 607, 610, 611, 2000, 2001, 2002, 2003, 2005,
                              2006, 2007, 2008, 2009, 2600, 2900, 2901, 2902, 2999]
        listitems = []
        for folder in self.xml_folders:
            window_ids = []
            window_refs = []
            control_refs = []
            defines = []
            for xml_file in self.window_file_list[folder]:
                path = os.path.join(self.project_path, folder, xml_file)
                root = get_root_from_file(path)
                if "id" in root.attrib:
                    window_ids.append(root.attrib["id"])
                # get all nodes with ids....
                xpath = ".//*[@id]"
                for node in root.xpath(xpath):
                    item = {"name": node.attrib["id"],
                            "type": node.tag,
                            "file": path,
                            "line": node.sourceline}
                    defines.append(item)
                # get all conditions....
                xpath = ".//*[@condition]"
                for node in root.xpath(xpath):
                    for match in re.finditer(control_regex, node.attrib["condition"], re.IGNORECASE):
                        item = {"name": match.group(1),
                                "type": node.tag,
                                "file": path,
                                "line": node.sourceline}
                        control_refs.append(item)
                    for match in re.finditer(window_regex, node.attrib["condition"], re.IGNORECASE):
                        item = {"name": match.group(1),
                                "type": node.tag,
                                "file": path,
                                "line": node.sourceline}
                        window_refs.append(item)
                bracket_tags = ["visible", "enable", "usealttexture", "selected", "onclick", "onback"]
                xpath = ".//" + " | .//".join(bracket_tags)
                for node in root.xpath(xpath):
                    if not node.text:
                        continue
                    for match in re.finditer(control_regex, node.text, re.IGNORECASE):
                        item = {"name": match.group(1),
                                "type": node.tag,
                                "file": path,
                                "line": node.sourceline}
                        control_refs.append(item)
                    for match in re.finditer(window_regex, node.text, re.IGNORECASE):
                        item = {"name": match.group(1),
                                "type": node.tag,
                                "file": path,
                                "line": node.sourceline}
                        window_refs.append(item)
                # check if all refs exist...
            define_list = [d['name'] for d in defines]
            for item in window_refs:
                if item["name"] in window_ids:
                    pass
                elif int(item["name"]) in builtin_window_ids:
                    pass
                else:
                    item["message"] = "Window ID not defined: " + item["name"]
                    listitems.append(item)
            for item in control_refs:
                if not item["name"] or item["name"] in define_list:
                    pass
                else:
                    item["message"] = "Control / Item ID not defined: " + item["name"]
                    listitems.append(item)
        return listitems

    def resolve_include(self, ref, folder):
        if not ref.text:
            return None
        include_names = [item["name"] for item in self.include_list[folder]]
        if ref.text not in include_names:
            return None
        index = include_names.index(ref.text)
        node = self.include_list[folder][index]
        root = ET.fromstring(node["content"])
        root = self.resolve_includes(root, folder)
        return root

    def resolve_includes(self, xml_source, folder):
        xpath = ".//include"
        for node in xml_source.xpath(xpath):
            if node.text:
                new_include = self.resolve_include(node, folder)
                if new_include is not None:
                    node.getparent().replace(node, new_include)
        return xml_source

    def check_labels(self):
        listitems = []
        refs = []
        regexs = [r"\$LOCALIZE\[([0-9].*?)\]", r"^(\d+)$"]
        label_regex = r"[A-Za-z]+"
        # labels = [s["string"] for s in self.string_list]
        checks = [[".//viewtype[(@label)]", "label"],
                  [".//fontset[(@idloc)]", "idloc"],
                  [".//label[(@fallback)]", "fallback"]]
        for folder in self.xml_folders:
            for xml_file in self.window_file_list[folder]:
                path = os.path.join(self.project_path, folder, xml_file)
                root = get_root_from_file(path)
                if root is None:
                    continue
                # find all referenced label ids (in element content)
                for element in root.xpath(".//label | .//altlabel | .//label2 | .//value | .//onclick | .//property"):
                    if not element.text:
                        continue
                    for regex in regexs:
                        for match in re.finditer(regex, element.text):
                            item = {"name": match.group(1),
                                    "type": element.tag,
                                    "file": path,
                                    "line": element.sourceline}
                            refs.append(item)
                # check for untranslated strings...
                for element in root.xpath(".//label | .//altlabel | .//label2"):
                    if not element.text:
                        continue
                    if "$" not in element.text and not element.text.isdigit() and re.match(label_regex, element.text):
                        item = {"name": element.text,
                                "type": element.tag,
                                "file": path,
                                "message": "Label in <%s> not translated: %s" % (element.tag, element.text),
                                "line": element.sourceline}
                        listitems.append(item)
                # find some more references (in attribute values this time)....
                for check in checks:
                    for element in root.xpath(check[0]):
                        attr = element.attrib[check[1]]
                        for regex in regexs:
                            for match in re.finditer(regex, attr):
                                item = {"name": match.group(1),
                                        "type": element.tag,
                                        "file": path,
                                        "line": element.sourceline}
                                refs.append(item)
                        # find some more untranslated strings
                        if "$" not in attr and not attr.isdigit() and re.match(label_regex, attr):
                            item = {"name": attr,
                                    "type": element.tag,
                                    "file": path,
                                    "message": "Label in attribute not translated: %s" % attr,
                                    "line": element.sourceline}
                            listitems.append(item)
        # check if refs are defined in po files
        label_ids = [s["id"] for s in self.string_list]
        for ref in refs:
            if "#" + ref["name"] not in label_ids:
                ref["message"] = "Label not defined: %s" % ref["name"]
                listitems.append(ref)
        return listitems

    def check_values(self):
        listitems = []
        for folder in self.xml_folders:
            for xml_file in self.window_file_list[folder]:
                path = os.path.join(self.project_path, folder, xml_file)
                new_items = self.check_file(path)
                listitems.extend(new_items)
        return listitems

    def check_file(self, path):
        xml_file = os.path.basename(path)
        # tags allowed for all controls
        common = ["description", "camera", "posx", "posy", "top", "bottom", "left", "right", "centertop", "centerbottom", "centerleft", "centerright", "width", "height", "visible", "include", "animation"]
        # tags allowed for containers
        list_common = ["focusedlayout", "itemlayout", "content", "onup", "ondown", "onleft", "onright", "onback", "orientation", "preloaditems", "scrolltime", "pagecontrol", "viewtype", "autoscroll", "hitrect"]
        # allowed child nodes for different control types (+ some other nodes)
        tag_checks = [[".//control[@type='button']/*", common + ["colordiffuse", "texturefocus", "texturenofocus", "label", "label2", "font", "textcolor", "disabledcolor", "selectedcolor", "shadowcolor", "align", "aligny", "textoffsetx", "textoffsety", "pulseonselect", "onclick", "onfocus", "onunfocus", "onup", "onleft", "onright", "ondown", "onback", "textwidth", "focusedcolor", "invalidcolor", "angle", "hitrect", "enable"]],
                      [".//control[@type='radiobutton']/*", common + ["colordiffuse", "texturefocus", "texturenofocus", "label", "selected", "font", "textcolor", "disabledcolor", "selectedcolor", "shadowcolor", "align", "aligny", "textoffsetx", "textoffsety", "pulseonselect", "onclick", "onfocus", "onunfocus", "onup", "onleft", "onright", "ondown", "onback", "textwidth", "focusedcolor", "angle", "hitrect", "enable", "textureradioonfocus", "textureradioofffocus", "textureradioonnofocus", "textureradiooffnofocus", "textureradioon", "textureradiooff", "radioposx", "radioposy", "radiowidth", "radioheight"]],
                      [".//control[@type='spincontrol']/*", common + ["colordiffuse", "textureup", "textureupfocus", "texturedown", "texturedownfocus", "spinwidth", "spinheight", "spinposx", "spinposy" "label", "subtype", "font", "textcolor", "disabledcolor", "shadowcolor", "align", "aligny", "textoffsetx", "textoffsety", "pulseonselect", "onfocus", "onunfocus", "onup", "onleft", "onright", "ondown", "onback", "hitrect", "enable", "showonepage"]],
                      [".//control[@type='togglebutton']/*", common + ["colordiffuse", "texturefocus", "alttexturefocus", "alttexturenofocus", "altclick", "texturenofocus", "label", "altlabel", "usealttexture", "font", "textcolor", "disabledcolor", "shadowcolor", "align", "aligny", "textoffsetx", "textoffsety", "pulseonselect", "onclick", "onfocus", "onunfocus", "onup", "onleft", "onright", "ondown", "onback", "textwidth", "focusedcolor", "subtype", "hitrect", "enable"]],
                      [".//control[@type='label']/*", common + ["align", "aligny", "scroll", "scrollout", "info", "number", "angle", "haspath", "label", "textcolor", "selectedcolor", "font", "shadowcolor", "disabledcolor", "pauseatend", "wrapmultiline", "scrollspeed", "scrollsuffix", "textoffsetx", "textoffsety"]],
                      [".//control[@type='textbox']/*", common + ["align", "aligny", "autoscroll", "label", "info", "font", "textcolor", "selectedcolor", "shadowcolor", "pagecontrol"]],
                      [".//control[@type='edit']/*", common + ["colordiffuse", "align", "aligny", "label", "hinttext", "font", "textoffsetx", "textoffsety", "pulseonselect", "textcolor", "disabledcolor", "invalidcolor", "focusedcolor", "shadowcolor", "texturefocus", "texturenofocus", "onclick", "onfocus", "onunfocus", "onup", "onleft", "onright", "ondown", "onback", "textwidth", "hitrect", "enable"]],
                      [".//control[@type='image']/*", common + ["align", "aligny", "aspectratio", "fadetime", "colordiffuse", "texture", "bordertexture", "bordersize", "info"]],
                      [".//control[@type='multiimage']/*", common + ["align", "aligny", "aspectratio", "fadetime", "colordiffuse", "imagepath", "timeperimage", "loop", "info", "randomize", "pauseatend"]],
                      [".//control[@type='scrollbar']/*", common + ["texturesliderbackground", "texturesliderbar", "texturesliderbarfocus", "textureslidernib", "textureslidernibfocus", "pulseonselect", "orientation", "showonepage", "pagecontrol", "onclick", "onfocus", "onunfocus", "onup", "onleft", "onright", "ondown", "onback"]],
                      [".//control[@type='progress']/*", common + ["texturebg", "lefttexture", "colordiffuse", "righttexture", "overlaytexture", "midtexture", "info", "reveal"]],
                      [".//control[@type='videowindow']/*", common],
                      [".//control[@type='visualisation']/*", common],
                      [".//control[@type='list']/*", common + list_common],
                      [".//control[@type='wraplist']/*", common + list_common + ["focusposition"]],
                      [".//control[@type='panel']/*", common + list_common],
                      [".//control[@type='fixedlist']/*", common + list_common + ["movement", "focusposition"]],
                      [".//content/*", ["item", "include"]],
                      [".//itemlayout/* | .//focusedlayout/*", ["control", "include"]],
                      ["/includes/*", ["include", "default", "constant", "variable"]],
                      ["/window/*", ["include", "defaultcontrol", "onload", "onunload", "controls", "allowoverlay", "views", "coordinates", "animation", "visible", "zorder", "fontset", "backgroundcolor"]],
                      ["/fonts/*", ["fontset"]],
                      [".//variable/*", ["value"]]]
        # allowed attributes for some specific nodes
        att_checks = [[["aspectratio"], ["align", "aligny", "scalediffuse"]],
                      [["texture"], ["background", "flipx", "flipy", "fallback", "border", "diffuse", "colordiffuse"]],
                      [["label"], ["fallback"]],
                      [["defaultcontrol"], ["always"]],
                      [["visible"], ["allowhiddenfocus"]],
                      [["align", "aligny", "posx", "posy", "textoffsetx", "textoffsety"], []],
                      [["height", "width"], ["min", "max"]],
                      [["camera"], ["x", "y"]],
                      [["hitrect"], ["x", "y", "w", "h"]],
                      [["onload", "onunload", "onclick", "onleft", "onright", "onup", "ondown", "onback", "onfocus", "onunfocus", "value"], ["condition"]],
                      [["property"], ["name", "fallback"]],
                      [["focusedlayout", "itemlayout"], ["height", "width", "condition"]],
                      [["item"], ["id"]],
                      [["control"], ["id", "type"]],
                      [["variable"], ["name"]],
                      [["include"], ["name", "condition", "file"]],
                      [["animation"], ["start", "end", "effect", "tween", "easing", "time", "condition", "reversible", "type", "center", "delay", "pulse", "loop", "acceleration"]],
                      [["effect"], ["start", "end", "tween", "easing", "time", "condition", "type", "center", "delay", "pulse", "loop", "acceleration"]]]
        # check correct parantheses for some nodes
        bracket_tags = ["visible", "enable", "usealttexture", "selected"]
        # check some nodes to use noop instead of "-" / empty
        noop_tags = ["onclick", "onfocus", "onunfocus", "onup", "onleft", "onright", "ondown", "onback"]
        # check that some nodes only exist once on each level
        # todo: special cases: label for fadelabel
        double_tags = ["camera", "posx", "posy", "top", "bottom", "left", "right", "centertop", "centerbottom", "centerleft", "centerright", "width", "height",
                       "colordiffuse", "texturefocus", "texturenofocus", "font", "selected", "textcolor", "disabledcolor", "selectedcolor",
                       "shadowcolor", "align", "aligny", "textoffsetx", "textoffsety", "pulseonselect", "textwidth", "focusedcolor", "invalidcolor", "angle", "hitrect"]
        # check that some nodes only contain specific text
        allowed_text = [[["align"], ["left", "center", "right", "justify"]],
                        [["aspectratio"], ["keep", "scale", "stretch", "center"]],
                        [["aligny"], ["top", "center", "bottom"]],
                        [["orientation"], ["horizontal", "vertical"]],
                        [["subtype"], ["page", "int", "float", "text"]],
                        [["action"], ["volume", "seek"]],
                        [["scroll", "randomize", "scrollout", "pulseonselect", "reverse", "usecontrolcoords"], ["false", "true", "yes", "no"]]]
        # check that some attributes may only contain specific values
        allowed_attr = [["align", ["left", "center", "right", "justify"]],
                        ["aligny", ["top", "center", "bottom"]],
                        ["flipx", ["true", "false"]],
                        ["flipy", ["true", "false"]]]
        root = get_root_from_file(path)
        folder = path.split(os.sep)[-2]
        # root = self.resolve_includes(root, folder)
        if root is None:
            return []
        tree = ET.ElementTree(root)
        listitems = []
        # find invalid tags
        for check in tag_checks:
            for node in root.xpath(check[0]):
                if node.tag not in check[1]:
                    if "type" in node.getparent().attrib:
                        text = '"%s type="%s"' % (node.getparent().tag, node.getparent().attrib["type"])
                    else:
                        text = node.getparent().tag
                    item = {"line": node.sourceline,
                            "type": node.tag,
                            "filename": xml_file,
                            "message": "invalid tag for <%s>: <%s>" % (text, node.tag),
                            "file": path}
                    listitems.append(item)
        # find invalid attributes
        for check in att_checks:
            xpath = ".//" + " | .//".join(check[0])
            for node in root.xpath(".//%s" % xpath):
                for attr in node.attrib:
                    if attr not in check[1]:
                        item = {"line": node.sourceline,
                                "type": node.tag,
                                "filename": xml_file,
                                "message": "invalid attribute for <%s>: %s" % (node.tag, attr),
                                "file": path}
                        listitems.append(item)
        # check conditions in element content
        xpath = ".//" + " | .//".join(bracket_tags)
        for node in root.xpath(xpath):
            if not node.text:
                message = "Empty condition: %s" % (node.tag)
            elif not check_brackets(node.text):
                condition = str(node.text).replace("  ", "").replace("\t", "")
                message = "Brackets do not match: %s" % (condition)
            else:
                continue
            item = {"line": node.sourceline,
                    "type": node.tag,
                    "filename": xml_file,
                    "message": message,
                    "file": path}
            listitems.append(item)
        # check conditions in attribute values
        for node in root.xpath(".//*[@condition]"):
            if not check_brackets(node.attrib["condition"]):
                condition = str(node.attrib["condition"]).replace("  ", "").replace("\t", "")
                item = {"line": node.sourceline,
                        "type": node.tag,
                        "filename": xml_file,
                        "message": "Brackets do not match: %s" % (condition),
                        "file": path}
                listitems.append(item)
        # check for noop as empty action
        xpath = ".//" + " | .//".join(noop_tags)
        for node in root.xpath(xpath):
            if node.text == "-" or not node.text:
                item = {"line": node.sourceline,
                        "type": node.tag,
                        "filename": xml_file,
                        "message": "Use 'noop' for empty calls <%s>" % (node.tag),
                        "file": path}
                listitems.append(item)
        # check for not-allowed siblings for some tags
        xpath = ".//" + " | .//".join(double_tags)
        for node in root.xpath(xpath):
            if not node.getchildren():
                xpath = tree.getpath(node)
                if xpath.endswith("]") and not xpath.endswith("[1]"):
                    item = {"line": node.sourceline,
                            "type": node.tag,
                            "filename": xml_file,
                            "message": "Invalid multiple tags for %s: <%s>" % (node.getparent().tag, node.tag),
                            "file": path}
                    listitems.append(item)
        # Check tags which require specific values
        for check in allowed_text:
            xpath = ".//" + " | .//".join(check[0])
            for node in root.xpath(xpath):
                if node.text.lower() not in check[1]:
                    item = {"line": node.sourceline,
                            "type": node.tag,
                            "filename": xml_file,
                            "message": "invalid value for %s: %s" % (node.tag, node.text),
                            "file": path}
                    listitems.append(item)
        # Check attributes which require specific values
        for check in allowed_attr:
            for node in root.xpath(".//*[(@%s)]" % check[0]):
                if node.attrib[check[0]] not in check[1]:
                    item = {"line": node.sourceline,
                            "type": node.tag,
                            "filename": xml_file,
                            "message": "invalid value for %s attribute: %s" % (check[0], node.attrib[check[0]]),
                            "file": path}
                    listitems.append(item)
        return listitems
