
import argparse, time, signal
running=True
def stop(*_):
    global running; running=False

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("queue",choices=["ingestion","reasoning","publication","maintenance"]); args=parser.parse_args()
    signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)
    print(f"worker_started queue={args.queue}",flush=True)
    # Bind lemp_pg.Worker and the component handlers here; idle loop keeps Railway service healthy.
    while running: time.sleep(5)
    print("worker_stopped",flush=True)
if __name__=="__main__": main()
