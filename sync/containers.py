import sys

import swiftclient
import eventlet

from sync.objects import sync_object


def sync_container(orig_storage_cnx, orig_storage_url,
                   orig_token, dest_storage_cnx,
                   dest_storage_url, dest_token,
                   container_name):
    orig_container_stats, orig_objects = swiftclient.get_container(
        None, orig_token, container_name, http_conn=orig_storage_cnx,
    )

    try:
        swiftclient.head_container(
            "", dest_token, container_name, http_conn=dest_storage_cnx
        )
    except(swiftclient.client.ClientException):
        container_headers = orig_container_stats.copy()
        for h in ('x-container-object-count', 'x-trans-id',
                  'x-container-bytes-used'):
            del container_headers[h]
        p = dest_storage_cnx[0]
        url = "%s://%s%s" % (p.scheme, p.netloc, p.path)
        swiftclient.put_container(url,
            dest_token, container_name,
            headers=container_headers)


    dest_container_stats, dest_objects = swiftclient.get_container(
        None, dest_token, container_name, http_conn=dest_storage_cnx,
    )

    set1 = set((x['hash'], x['name']) for x in orig_objects)
    set2 = set((x['hash'], x['name']) for x in dest_objects)
    diff = set1 - set2
    if not diff:
        return

    pool = eventlet.GreenPool()
    cnt = 0
    for obj in diff:
        pool.spawn_n(sync_object,
                     orig_storage_url,
                     orig_token,
                     dest_storage_url,
                     dest_token, container_name,
                     obj)
        if cnt == 20:
            pool.waitall()
            cnt = 0
        else:
            cnt += 1

    pool.waitall()