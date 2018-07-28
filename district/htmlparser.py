#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging as log
import re
from html.parser import HTMLParser
from urllib import request
import time
import json
from collections import Iterable


class DistrictParser(HTMLParser):
    """
        a parser to parse data from gov stats
    """

    __DISTRICT_TYPES = ['province', 'city', 'county', 'town', 'village']

    __TR_HEAD_PATTERN = r'(\w+)head'

    __TR_DATA_PATTERN = r'(\w+)tr'

    __HREF_PATTERN = r'^(\d+/)*([\d/]+)\.html$'

    __DEF_MAP = {'统计用区划代码': 'code', '名称': 'name'}

    def __init__(self, host_node=None, path=''):
        HTMLParser.__init__(self)
        self.__node_list = []
        self.__host_node = host_node
        self.__parse_ctx = dict()
        self.__path = str(path)

    @property
    def host_node(self):
        return self.__host_node

    @property
    def path(self):
        return self.__path

    @property
    def node_list(self):
        return self.__node_list

    def handle_starttag(self, tag, attrs):
        # print('start:', tag)
        attrs_map = dict(attrs)
        cls = attrs_map.get('class')
        head_match = data_match = None
        if cls:
            head_match = re.match(DistrictParser.__TR_HEAD_PATTERN, cls)
            data_match = re.match(DistrictParser.__TR_DATA_PATTERN, cls)
        self.__parse_ctx['curr_tag'] = tag
        if tag == 'tr' and data_match:
            node_type = data_match.group(1)
            if node_type in DistrictParser.__DISTRICT_TYPES:
                self.__parse_ctx['row_type'] = 'data'
                self.__parse_ctx['node_type'] = node_type
                self.__reset_index()
                if self.__parse_ctx.get('has_head', False):
                    self.__create_new_node()
            else:
                print("unsupported type:", node_type)
        elif tag == 'tr' and self.__curr_level() > 1 and head_match:
            node_type = head_match.group(1)
            if node_type in DistrictParser.__DISTRICT_TYPES:
                self.__parse_ctx['row_type'] = 'head'
                self.__parse_ctx['has_head'] = True
                self.__parse_ctx['node_type'] = node_type
                self.__create_def_map()
                self.__reset_index()
            else:
                print("unsupported type:", node_type)
        elif tag in ['a', 'td'] and self.__parse_ctx.get('row_type'):
            if tag == 'td':
                self.__inc_index()
            self.__parse_ctx['do_body'] = True
            href = attrs_map.get('href')
            if self.path and href:
                self.__parse_ctx['href'] = self.path + '/' + href
            else:
                self.__parse_ctx['href'] = href

    def __curr_level(self):
        if self.host_node is None:
            return 1
        else:
            return self.host_node.get('level') + 1

    def __create_new_node(self):
        node_type = self.__parse_ctx.get('node_type')
        if self.host_node is None:
            level = 1
            p_code = None
        else:
            level = self.host_node.get('level') + 1
            p_code = self.host_node.get('code')
        node = {'code': None, 'p_code': p_code, 'level': level, 'name': None, 'href': None, 'type': node_type}
        self.__curr_node(node)
        self.__node_list.append(node)
        # print('create a node:', node)
        return node

    def __create_def_map(self):
        self.__parse_ctx['def_map'] = {}

    def __put_def_map(self, data):
        idx = self.__parse_ctx.get('index')
        if idx is not None:
            map_val = DistrictParser.__DEF_MAP.get(data)
            if map_val is not None:
                # print('put def map:', idx, map_val)
                self.__parse_ctx.get('def_map')[idx] = map_val

    def __create_or_get_def_map(self):
        def_map = self.__parse_ctx.get('DefMap')
        if def_map is None:
            def_map = {}
            self.__parse_ctx['DefMap'] = def_map
        return def_map

    def __inc_index(self):
        self.__parse_ctx['index'] = self.__parse_ctx.get('index', 0) + 1

    def curr_index(self):
        return self.__parse_ctx.get('index')

    def __reset_index(self):
        self.__parse_ctx['index'] = 0

    def __init_ctx(self, tag):
        if tag == 'tr':
            self.__parse_ctx['row_type'] = None
            self.__parse_ctx['curr_node'] = None
        self.__parse_ctx['do_body'] = False

    def handle_endtag(self, tag):
        # print('end:', tag)
        self.__init_ctx(tag)

    @property
    def curr_node(self):
        return self.__parse_ctx.get('curr_node')

    def __curr_node(self, node):
        self.__parse_ctx['curr_node'] = node

    def handle_data(self, data):
        if self.__parse_ctx.get('do_body'):
            href = self.__parse_ctx.get('href')
            if self.__parse_ctx.get('has_head', False):
                if self.__parse_ctx.get('row_type') == 'head':
                    self.__put_def_map(data.strip())
                else:
                    node = self.curr_node
                    # print('handle data has head:', href, self.__parse_ctx.get('def_map'), self.curr_index(), data.strip())
                    def_map = self.__parse_ctx['def_map']
                    idx = self.curr_index()
                    if idx in def_map:
                        node[def_map[idx]] = data.strip()
                    node['href'] = href
            else:
                node = self.__create_new_node()
                node['name'] = data.strip()
                if href is not None:
                    matcher_groups = re.match(DistrictParser.__HREF_PATTERN, href).groups()
                    if len(matcher_groups) > 0:
                        node['code'] = matcher_groups[-1]
                node['href'] = href
                # print('handle data miss head:', href, node)

    def error(self, message):
        print(message)


base_url = 'http://www.stats.gov.cn/tjsj/tjbz/tjyqhdmhcxhfdm/2017/'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.96 Safari/537.36'
}


def fetch_data(url):
    req = request.Request(base_url + url, headers=headers)
    with request.urlopen(req) as r:
        data = r.read().decode('gbk')
        # print(data)
        return data


def proc_data(whole_list: Iterable, retry_list: Iterable, node=None, base_path='', url='index.html'):
    parser = DistrictParser(node, base_path)
    href = node.get('href') if node else None
    use_url = href if href else url
    parser.feed(fetch_data(use_url))
    node_list = parser.node_list
    while len(node_list):
        n = node_list[0]
        del node_list[0]
        whole_list.append(n)
        print(n)
        a_href = n.get('href', None)
        path = ''
        if a_href is not None:
            split_arr = a_href.split('/')
            if len(split_arr) > 1:
                path = '/'.join(split_arr[0:-1])
                # disParser = DistrictParser(n, '/'.join(split_arr[0:-1]))
            inner_parser = DistrictParser(n, path)
            try:
                inner_parser.feed(fetch_data(a_href))
                node_list = node_list + inner_parser.node_list
            except BaseException as e:
                print("except:", e, a_href)
                a_retry = {
                    'href': a_href,
                    'node': n,
                    'path': path
                }
                retry_list.append(a_href)
                continue
            finally:
                inner_parser.close()
    parser.close()


if __name__ == '__main__':
    whole_node_list = []
    retries = []

    proc_data(whole_node_list, retries)

    print(retries)
    print(len(whole_node_list))
    with open('/Users/easense/Downloads/district.json', 'w') as dj:
        json.dump(whole_node_list, dj, ensure_ascii=False)
