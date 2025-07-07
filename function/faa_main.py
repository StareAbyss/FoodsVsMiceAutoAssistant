import sys
import multiprocessing
from function.globals.loadings import loading, app
def main():
    def delayed_init(app, loading):
        from function.core.qmw_3_service import faa_start_main
        faa_start_main(app, loading)
    #锁定主进程
    multiprocessing.freeze_support()
    #展示加载窗口
    loading.show()
    loading.update_progress(1)
    loading.anim.start()
    delayed_init(app, loading)
    sys.exit(app.exec())





if __name__ == '__main__':
    main()