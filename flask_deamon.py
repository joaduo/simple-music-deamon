from flask import Flask
import json
import player_resource
import os
import settings
import logging
import traceback

app = Flask(__name__)

@app.route('/playlist_rscr/<action>', methods=['POST'])
def playlist_rscr(action):
    return serve('playlist_rscr', action)

@app.route('/')
def index_rscr():
    return serve('index_rscr')


@app.route('/directory_rsrc', methods=['POST'])
def directory_rsrc():
    return serve('directory_rsrc')


def serve(funcname, *args, **kwargs):
    try:
        return _serve_reload_module(funcname, *args, **kwargs)
    except Exception as e:
        logging.exception('Serving %s', funcname)
        trace = traceback.format_exc()
        return json.dumps(dict(err='Exc: %s %r! \n%s' % (e,e, trace)))

last_mtime = None
def _serve_reload_module(funcname, *args, **kwargs):
    pr = player_resource
    global last_mtime
    mod_path = player_resource.__file__.replace('.pyc','.py')
    mtime = os.path.getmtime(mod_path)
    if settings.RELOAD_MODE and last_mtime != mtime:
        last_mtime = mtime
        pr = reload(player_resource)
    return getattr(pr, funcname)(*args, **kwargs)


def main():
    try:
        app.run(host='0.0.0.0', port=8080)
    except Exception:
        logging.exception('Running server')
        raise


if __name__ == '__main__':
    main()
