"""Run with sdn-env/bin/python; Mininet runs separately with system Python."""
import argparse
import logging
import os
from pathlib import Path
from os_ken import cfg
from os_ken.base import app_manager
from os_ken.lib import hub

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--results',default='results/live')
    parser.add_argument('--port',type=int,default=6653)
    args=parser.parse_args()
    os.environ['SMARTCDN_RESULTS']=str(Path(args.results).resolve())
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
    # Import handler to register its configuration options before parsing.
    from os_ken.controller import ofp_handler
    cfg.CONF(args=['--ofp-tcp-listen-port',str(args.port),'--ofp-listen-host','127.0.0.1'],project='os_ken')
    manager=app_manager.AppManager.get_instance()
    try:
        manager.load_apps(['os_ken.controller.ofp_handler','simple_switch_13'])
        services=manager.instantiate_apps(**manager.create_contexts())
        hub.joinall(services)
    except KeyboardInterrupt:
        pass
    finally:
        manager.close()

if __name__=='__main__':
    main()
