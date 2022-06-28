import os
import io
import time
import posixpath
import urllib
import urllib.parse
import argparse
import traceback
import pickle

import tqdm
import bs4

import cacherequests


def normalize_url(url):
    # remove # and query string
    split_result = urllib.parse.urlsplit(url)
    # split_result.query = ''
    # split_result.fragment = ''

    # return urllib.parse.urlunsplit(split_result)
    return urllib.parse.urlunsplit((
        split_result.scheme,
        split_result.netloc,
        split_result.path,
        '',
        '',
    ),)


def is_from_oracle(url: str):
    return ('docs.oracle.com' in url)
    # split_result = urllib.parse.urlsplit(url)
    # return (split_result.netloc == 'docs.oracle.com')


IGNORED_EXTENSIONS = [
    '.gif'
]


def decode_html_bs(html_bs):
    try:
        return html_bs.decode('utf-8')
    except UnicodeDecodeError:
        pass

    try:
        return html_bs.decode('iso-8859-1')
    except UnicodeDecodeError:
        pass

    try:
        return html_bs.decode('utf-16')
    except UnicodeDecodeError:
        pass

    try:
        return html_bs.decode('utf-32')
    except UnicodeDecodeError:
        pass

    raise Exception('Could not decode HTML')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('urllistfile', type=str, help='file containing urls')

    args = parser.parse_args()
    print('args', args)

    content_bs = open(args.urllistfile, 'rb').read()
    content_str = content_bs.decode('utf-8')
    url_list = content_str.splitlines()

    url_list = list(filter(lambda x: len(x) > 0, url_list))
    url_list = [normalize_url(url) for url in url_list]
    url_set = set(url_list)
    url_list = list(url_set)
    url_list = list(filter(lambda x: is_from_oracle(x), url_list))

    parsed_url_list = []
    parsed_url_set = set()
    new_url_list = []

    base_parsed_url_list_log_filepath = 'parsed_url_list.txt'
    if os.path.exists(base_parsed_url_list_log_filepath):
        content_bs = open(base_parsed_url_list_log_filepath, 'rb').read()
        content_str = content_bs.decode('utf-8')
        parsed_url_list = content_str.splitlines()
        parsed_url_list = list(filter(lambda x: len(x) > 0, parsed_url_list))
        parsed_url_set = set(parsed_url_list)
        parsed_url_list = list(parsed_url_set)

    error_log = []
    more_url_list = []
    pbar = tqdm.tqdm(url_list)

    for url in pbar:
        if os.path.exists('stop'):
            print('stop file found, exiting')
            os.remove('stop')
            exit(1)

        pbar.set_description(url)

        if url in parsed_url_set:
            continue

        try:
            response_obj = cacherequests.wrap_requests(
                url=url,
                check_body_size=False,
            )

            if response_obj['status_code'] != 200:
                error_log.append({
                    'url': url,
                    'status_code': response_obj['status_code'],
                })

                continue

            ext = os.path.splitext(url)[1]
            ext = ext.lower()
            if ext in IGNORED_EXTENSIONS:
                new_url_list.append(url)
                continue

            content_str = decode_html_bs(response_obj['content_bs'])
            soup = bs4.BeautifulSoup(content_str)

            frame_element_list = soup.select('frame')
            for frame_element in frame_element_list:
                try:
                    frame_url = frame_element.attrs['src']
                    frame_url = urllib.parse.urljoin(url, frame_url)
                    more_url_list.append(frame_url)
                except:
                    pass

            a_element_list = soup.select('a')
            for a_element in a_element_list:
                try:
                    a_url = a_element.attrs['href']
                    a_url = urllib.parse.urljoin(url, a_url)
                    more_url_list.append(a_url)
                except:
                    pass

            img_element_list = soup.select('img')
            for img_element in img_element_list:
                try:
                    img_url = img_element.attrs['src']
                    img_url = urllib.parse.urljoin(url, img_url)
                    more_url_list.append(img_url)
                except:
                    pass

            new_url_list.append(url)
        except Exception as ex:
            stacktrace = traceback.format_exc()
            error_log.append({
                'url': url,
                'exception': str(ex),
                'stacktrace': stacktrace,
            })

    if len(error_log) > 0:
        log_filepath = f'error_log-{time.time_ns()}.pickle'
        print('error_log', log_filepath)
        with open(log_filepath, 'wb') as outfile:
            pickle.dump(error_log, outfile)

        print(error_log)

    print('', flush=True)
    print('len(more_url_list)', len(more_url_list), flush=True)

    more_url_list = list(map(lambda url: normalize_url(url), more_url_list))
    more_url_list_set = set(more_url_list)
    more_url_list = list(more_url_list_set - url_set)
    print('len(more_url_list)', len(more_url_list), flush=True)

    if len(more_url_list) > 0:
        log_filepath = f'more_url_list-{time.time_ns()}.txt'
        print('more_url_list', log_filepath)
        with open(log_filepath, 'wb') as outfile:
            outfile.write('\n'.join(more_url_list).encode('utf-8'))

    more_url_list = map(lambda url: url.strip(), more_url_list)
    more_url_list = map(lambda url: normalize_url(url), more_url_list)
    more_url_list = map(lambda url: url.strip(), more_url_list)
    more_url_list = filter(lambda url: len(url) > 0, more_url_list)
    more_url_list = filter(lambda url: is_from_oracle(url), more_url_list)
    more_url_list = list(more_url_list)

    print('len(more_url_list)', len(more_url_list), flush=True)
    if len(more_url_list) > 0:
        log_filepath = f'more_url_list-filtered-{time.time_ns()}.txt'
        print(log_filepath)
        with open(log_filepath, 'wb') as outfile:
            outfile.write('\n'.join(more_url_list).encode('utf-8'))

    print('len(new_url_list)', len(new_url_list), flush=True)
    if len(new_url_list) > 0:
        parsed_url_list.extend(new_url_list)
        if os.path.exists(base_parsed_url_list_log_filepath):
            basename, ext = os.path.splitext(base_parsed_url_list_log_filepath)
            backup_filepath = f'{basename}-{time.time_ns()}{ext}'
            os.rename(base_parsed_url_list_log_filepath, backup_filepath)

        with open(base_parsed_url_list_log_filepath, 'wb') as outfile:
            outfile.write('\n'.join(parsed_url_list).encode('utf-8'))


if __name__ == '__main__':
    main()
