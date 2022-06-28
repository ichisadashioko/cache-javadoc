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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url', type=str, help='starting url')

    args = parser.parse_args()
    print('args', args)

    url_list = [args.url]

    parsed_url = []

    while len(url_list) > 0:
        log_filepath = f'url_list-{time.time_ns()}.txt'
        with open(log_filepath, 'wb') as outfile:
            for url in url_list:
                outfile.write(url.encode('utf-8'))
                outfile.write(b'\n')

        if os.path.exists('stop'):
            print('stop file found, exiting')
            os.remove('stop')

            exit(1)

        url_list = list(map(lambda url: normalize_url(url), url_list))
        url_list_set = set(url_list)
        parsed_url_set = set(parsed_url)
        new_url_list = list(url_list_set - parsed_url_set)
        url_list = new_url_list

        ignored_url_list = []
        todo_url_list = []

        for url in url_list:
            if is_from_oracle(url):
                todo_url_list.append(url)
            else:
                ignored_url_list.append(url)

        if len(ignored_url_list) > 0:
            log_filepath = f'ignored_url_list-{time.time_ns()}.txt'
            print(len(ignored_url_list), log_filepath)
            with open(log_filepath, 'wb') as outfile:
                for url in ignored_url_list:
                    outfile.write(url.encode('utf-8'))
                    outfile.write(b'\n')

        error_log = []
        more_url_list = []
        pbar = tqdm.tqdm(url_list)

        for url in pbar:
            if os.path.exists('stop'):
                print('stop file found, exiting')
                os.remove('stop')
                exit(1)

            pbar.set_description(url)
            parsed_url.append(url)

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

                content_str = response_obj['content_bs'].decode('utf-8')
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
        if len(more_url_list) == 0:
            break

        more_url_list = list(map(lambda url: normalize_url(url), more_url_list))
        more_url_list_set = set(more_url_list)
        more_url_list = list(more_url_list_set - parsed_url_set)
        url_list = more_url_list


if __name__ == '__main__':
    main()
