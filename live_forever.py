from apscheduler.schedulers.blocking import BlockingScheduler

forever_schedule = BlockingScheduler()


@forever_schedule.scheduled_job('interval', minutes=15)
def wake_up():
    print('Wake up!')
