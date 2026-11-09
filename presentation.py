"""Readable demo narration. Every outcome and route comes from this run's data."""
import csv
import json
from collections import Counter
from pathlib import Path
from network_config import HOSTS, VIP


def say(message=''):
    print(message, flush=True)


def stage(title, explanation):
    say('\n' + '=' * 76)
    say(title)
    say(explanation)
    say('=' * 76)


def topology():
    stage('SMART CONTENT DELIVERY SYSTEM | LIVE SDN DEMONSTRATION',
          '6 clients | 4 replicated content servers | 6 OpenFlow 1.3 switches')
    say(r"""
               OS-Ken controller -- OpenFlow 1.3 to ALL switches

                      s1 -------50------- s2
                      |
                     30
                      |
    srv1,srv2 ------ s3 --------10------- s4 ------ srv3,srv4
                      |                   |
                     20                  20
                      |                   |
    c1,c2,c3 ------- s5 --------10------- s6 ------ c4,c5,c6

    Additional redundant links: s1--s4 (30), s2--s5 (40), s2--s6 (40).
    Numbers = Mbps; ALL inter-switch links have 5 ms delay.
    ALL host links = 100 Mbps / 2 ms.
    Service: 10.0.0.100:5000 -> controller selects srv1/srv2/srv3/srv4.
""")
    say('Servers: srv1=.11, srv2=.12, srv3=.13, srv4=.14 (10.0.0.x)')
    say('Clients: c1=.21, c2=.22, c3=.23, c4=.24, c5=.25, c6=.26')
    say('Switch fabric: s1-s2, s1-s3, s1-s4, s2-s5, s2-s6,')
    say('               s3-s5, s4-s6, s3-s4, s5-s6. No broadcast flooding.')


def verdict(passed, title, detail=''):
    say(f'[{"PASS" if passed else "FAIL"}] {title}' + (f' | {detail}' if detail else ''))


def decision_for(output, client, client_port):
    if not client_port:
        return None
    ip = next((ip for ip,host in HOSTS.items() if host['name'] == client),None)
    try:
        with (Path(output)/'decisions.csv').open() as stream:
            records = list(csv.DictReader(stream))
        return next((row for row in reversed(records)
                     if row['client']==ip and int(row['client_port'])==int(client_port)),None)
    except (OSError,ValueError,KeyError,TypeError):
        return None


def show_request(output, row):
    if not row['ok']:
        verdict(False, f'{row["client"]}: {row["content"]}', row.get('error') or 'Transfer did not complete')
        return
    verdict(True, f'{row["client"]} received {row["content"]} from {row["server"]}',
            f'SHA-256 verified | {row["bytes"]:,} bytes | {row["response_s"]:.3f} s | {row["throughput_mbps"]:.2f} Mbps')
    decision = decision_for(output,row['client'],row.get('client_port'))
    if decision:
        switches = ' -> '.join('s'+node for node in decision['path'].split('-'))
        say(f'       Controller-selected request route: {row["client"]} -> {switches} -> {row["server"]}')
        say(f'       Return traffic uses reverse forwarding with source translated to {VIP}.')
        say(f'       Decision: score={float(decision["score"]):.2f} (lower is better), '
            f'active transfers={decision["active"]}, server traffic={float(decision["mbps"]):.2f} Mbps')
    else:
        say('       Matching controller decision not yet available; no route is inferred.')


def snapshot(output):
    try:
        state=json.loads((Path(output)/'controller.json').read_text())
        say('Controller sees: '+', '.join('s'+str(n) for n in state['switches']))
        for ip,health in sorted(state.get('health',{}).items()):
            name=HOSTS.get(ip,{}).get('name',ip)
            say(f'  {name}: {"HEALTHY" if health.get("healthy") else "UNAVAILABLE"}, '
                f'active={health.get("active",0)}, measured={health.get("mbps",0):.2f} Mbps')
        down=state.get('down_links',[])
        unique=sorted({tuple(sorted(pair)) for pair in down})
        say('Unavailable switch links: '+(', '.join(f's{a}--s{b}' for a,b in unique) or 'none'))
    except (OSError,ValueError,KeyError,TypeError):
        say('Controller snapshot not available yet.')


def batch_summary(rows):
    successful=[row for row in rows if row['ok']]
    count=Counter(row['server'] for row in successful)
    say(f'Batch result: {len(successful)}/{len(rows)} verified transfers; '
        + ', '.join(f'{server}={number}' for server,number in sorted(count.items())))
    if successful:
        say(f'Mean completion time: {sum(row["response_s"] for row in successful)/len(successful):.3f} s')


CHECKS = {
    'all_six_clients': 'Every baseline request from all six clients completed and passed SHA-256',
    'multiple_servers': 'Baseline requests used at least two different servers',
    'image.jpg': 'All six clients received image.jpg correctly',
    'music.mp3': 'All six clients received music.mp3 correctly',
    'video.mp4': 'All six clients received video.mp4 correctly',
    'congestion_requests': 'VIP requests completed while competing TCP transfers were running',
    'server_recovered': 'A new verified transfer succeeded after srv1 was stopped',
    'failed_server_avoided': 'Every failure-phase request succeeded without selecting srv1',
    'link_recovered': 'A new verified transfer succeeded with an inter-switch link disabled',
    'link_failure_requests': 'All link-failure-phase requests completed successfully',
    'restored_requests': 'All six clients completed requests after the experiments',
}


def final_summary(checks, output):
    stage('FINAL EVALUATION', 'PASS means the measured check below succeeded; FAIL needs investigation.')
    for key,value in checks.items():
        verdict(value,CHECKS.get(key,key))
    say(f'\nEvidence and CSV files: {output}')
    say('Routes above are controller decisions, not packet-capture traces.')
    say('A deliberately stopped server/link is a test fault, not itself a failed test.')
    say('A failed transfer, unavailable route, or failed recovery check is a real failure.')
