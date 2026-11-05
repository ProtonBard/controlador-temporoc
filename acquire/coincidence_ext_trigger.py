from src.common_setup import *
from src.temporoc3 import *
from analyse.common_analysis_TDC import *


def coincidence_without_SiPM_dual_board_but_ext_trigger(board_master, board_slave, local_output_dir ="../output/coincidence/ext_trigger_digital/"):
    # use MASTER FPGA pulser to inject events through ext trigger

    config = {'board': [board_master, board_slave],
              'config_B%d'%board_master: {'mode': 'master', 'board': board_master},
              'config_B%d'%board_slave : {'mode': 'slave',  'board': board_slave}}

    local_output_dir += "B%d-%d/"%(board_master, board_slave)
    find_new_folder_index(local_output_dir, config)

    master = temporoc3(config, mode='master')
    slave = temporoc3(config, mode='slave')

    print("Make sure jumper JU13 is connnected on the right (close to the SMA Trig ext) on both boards !")

    setup_temporoc([master, slave], config, ext_trigger=True)
    config['test'] = "CTR between 2 boards with external trigger "

    # Optional config to be loaded
    extra_config = {'enabled_TH_fb': False, 'deserialiser_time': 0,
                   'enabled_ASIC_ch': [[]], 'enable_TL_ASIC_ch': [[12, 30]],
                   'calib_time_discri': False, 'calib_inDAC': False}

    for board in config['board']:
        config['config_B%d'%board].update(extra_config)
    load_config([master, slave], config)

    # External trigger specific
    master.asic.ch.group(master.board_config['enable_TL_ASIC_ch'][0]).select.trigTL.external()
    slave.asic.ch.group(slave.board_config['enable_TL_ASIC_ch'][0]).select.trigTL.external()
    master.board_config['tdc_injected'] = [['low']]
    slave.board_config['tdc_injected'] = [['low']]

    reset_FPGA_FIFO_and_tempo_digital([master, slave])  # Only ONCE at startup

    # Start signal injection!
    master.fpga.pulser.unmask_on_IO0()

    # acquire in loop
    acquire_data_multi_boards(10000, config, [master, slave])

    master.close()
    slave.close()


if __name__ == "__main__":
    coincidence_without_SiPM_dual_board_but_ext_trigger(6, 4)
