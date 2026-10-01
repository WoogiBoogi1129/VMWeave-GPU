"""Reuse dedicated monitoring; add only this campaign's scrape and dashboard."""
from common import *
import yaml,shutil
p=ROOT/'.local/performance-20260930/monitoring/prometheus.yml'
shutil.copy2(p,BASE/'prometheus-before.yml')
d=yaml.safe_load(p.read_text());assert not any(x['job_name']=='system-comparison' for x in d['scrape_configs'])
d['scrape_configs'].append({'job_name':'system-comparison','scrape_interval':'1s','static_configs':[{'targets':['192.168.24.21:9899']}]})
p.write_text(yaml.safe_dump(d,sort_keys=False))
k('exec','-n','vmweave-performance','perf-monitor','-c','prometheus','--','sh','-c','kill -HUP 1')
dashboard=json.loads((ROOT/'experiments/shm-first-bundle/grafana-dashboard.json').read_text())
dashboard.update({'uid':'vmweave-system-comparison','title':'VMWeave TCP/RPC vs improved SHM — whole systems'})
for panel in dashboard['panels']:
 if panel['title']=='Pod memory — Worker and launcher':panel['title']='Pod memory — runtime and launcher'
 if panel['title']=='Requested HAMi cap':
  panel['title']='Configured compute level — full GPU'
  panel['description']='100 is HAMi FORCE 100 for S and all 188 physical SMs through MPS for T. This panel records configuration, not measured utilization or quota compliance.'
save(ROOT/'.local/performance-20260930/monitoring/dashboards/system-comparison.json',dashboard)
save(OUT/'monitoring/grafana-dashboard.json',dashboard)
save(OUT/'monitoring/prometheus-config.json',d)
