import os
import sys
import logging
import time

from Pegasus.tools import utils
from Pegasus.shadowq.dag import parse_dag
from Pegasus.shadowq.jobstate import JSLog
from Pegasus.shadowq.wfmonitor import WorkflowMonitor
from Pegasus.shadowq.provision import Provisioner
from Pegasus.shadowq.messaging import ManifestListener, RequestPublisher

__all__ = ["main"]

log = logging.getLogger(__name__)

def main():
    if len(sys.argv) != 2:
        print "Usage: %s DAGFILE" % sys.argv[0]
        exit(1)

    utils.configureLogging(logging.INFO)

    log.info("Shadow queue starting...")

    dag_file = sys.argv[1]
    dag_file = os.path.join(os.getcwd(), dag_file)
    dag_file = os.path.abspath(dag_file)

    wf_dir = os.path.dirname(dag_file)

    jslog_file = os.path.join(wf_dir, "jobstate.log")

    braindump = utils.slurp_braindb(wf_dir)

    wf_uuid = braindump["wf_uuid"]

    log.info("wf_uuid: %s", wf_uuid)
    log.info("DAG: %s", dag_file)
    log.info("Workflow Dir: %s", wf_dir)
    log.info("Jobstate Log: %s", jslog_file)

    if not os.path.isfile(dag_file):
        log.error("DAG not found")
        exit(1)

    if not os.path.isdir(wf_dir):
        log.error("Workflow directory not found")
        exit(1)

    # Give it a few seconds for the jobstate.log file to be created
    for i in range(0, 15):
        if os.path.isfile(jslog_file):
            break
        time.sleep(1)

    if not os.path.isfile(jslog_file):
        log.error("Jobstate log not found")
        exit(1)

    # Change working directory
    os.chdir(wf_dir)

    dag = parse_dag(dag_file)
    jslog = JSLog(jslog_file)

    monitor = WorkflowMonitor(dag, jslog)
    monitor.start()

    slots = int(os.getenv("SHADOWQ_SLOTS", 1))
    estimates = os.getenv("SHADOWQ_ESTIMATES", None)
    interval = int(os.getenv("SHADOWQ_PROVISIONER_INTERVAL", 60))
    deadline = int(os.getenv("SHADOWQ_DEADLINE", 0))
    amqp_url = os.getenv("SHADOWQ_AMQP_URL")
    sliceid = os.getenv("SHADOWQ_SLICEID")

    listener = ManifestListener(amqp_url, sliceid)
    listener.start()

    publisher = RequestPublisher(amqp_url, sliceid, wf_uuid)

    provisioner = Provisioner(dag, estimates, interval, deadline, listener, publisher)
    provisioner.start()

    monitor.join()

    log.info("Shadow queue exiting")
