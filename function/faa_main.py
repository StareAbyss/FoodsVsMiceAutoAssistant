import multiprocessing
import sys

from function.globals.loadings import loading, app


def main():

    def delayed_init(app, loading):
        from function.core.qmw_3_service import faa_start_main
        faa_start_main(app, loading)

    # 锁定主进程
    multiprocessing.freeze_support()
    # 启动主程序时显式检查并补齐必需目录，避免导入 PATHS 时产生文件系统副作用
    from function.globals.get_paths import check_paths
    check_paths()
    # 展示加载窗口
    loading.show()
    loading.update_progress(1)
    loading.anim.start()
    delayed_init(app, loading)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
