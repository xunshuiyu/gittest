from PyQt5.QtCore import pyqtSignal, QThread
from params import *
from CanMonitor import *
from ctypes import *
from PyQt5.QtWidgets import QApplication, QMainWindow,QWidget,QMenu,QGridLayout,QHBoxLayout,QVBoxLayout,QTableWidget,QTableWidgetItem
from PyQt5.QtGui import QIcon, QColor, QBrush, QFont
import sys
import bitstring
import datetime
import time
import copy
import sqlite3
from database_test import *
from MyLog import *

class MyThread_TransRecv(QThread):
    #boardnum chipid 进度 状态 开始时间 耗时
    tbvcontentsignal = pyqtSignal(int, str, int, str, str, float)
    def __init__(self, ui):
        super().__init__()
        self.ui = ui
    def run(self):
        MyLog.get_log("info", "数据开始传输......")
        #将JSON文件的读取先放到这里，后期再开辟新的线程
        self.itemInfoGet()
        # while True:
        #     QThread.sleep(1000)

        #循环接收数据，并进行处理
        #初始通道
        vci_initconfig = VCI_INIT_CONFIG(0x80000008, 0xFFFFFFFF, 0,
                                         0, 0x03, 0x1C, 0)  # 波特率125k，正常模式
        ret = canDLL.VCI_InitCAN(VCI_USBCAN2, 0, Params.CAN_CH, byref(vci_initconfig))
        if ret == STATUS_OK:
            print('调用 VCI_InitCAN2 成功\r\n')
        if ret != STATUS_OK:
            print('调用 VCI_InitCAN2 出错\r\n')

        ret = canDLL.VCI_StartCAN(VCI_USBCAN2, 0, 1)
        if ret == STATUS_OK:
            print('调用 VCI_StartCAN2 成功\r\n')
        if ret != STATUS_OK:
            print('调用 VCI_StartCAN2 出错\r\n')
        vci_can_obj_tx = VCI_CAN_OBJ()  # 单次发送
        vci_can_obj_rx = VCI_CAN_OBJ()  # 单次发送

        trdb = trDB()
        trdb.openDb()
        while True:
            self.msleep(5)
            # 超时判断

            for i in Params.timeOut_dict:
                if(Params.boardstate_dict[i] == 1):
                    timeintervl = time.clock() - Params.timeOut_dict[i]
                    #Params.timeOut_dict[i] = time.clock()
                    if timeintervl > 10:
                        print("timeout.............")
                        timeconsume = 10
                        self.tbvcontentsignal.emit(i, str(Params.chipId_dict[i]), -1, "测试超时",
                                                   '', float('%04f' % timeconsume))
                        Params.timeOut_dict[i] = time.clock()
                        Params.boardTimeOut.append(i)
            for i in Params.boardTimeOut:
                # 这里需要做一些清理工作
                Params.timeOut_dict.pop(i)
                Params.timeStart_dict.pop(i)
                Params.chipId_dict.pop(i)
                Params.boardstate_dict.pop(i)
                Params.id_chip[i].clear()
            Params.boardTimeOut.clear()


            #print("VCI_Receive....")
            ret = canDLL.VCI_Receive(VCI_USBCAN2, 0, Params.CAN_CH, byref(vci_can_obj_rx), 1, 0)

            ################################判断帧的类型#########################
            if (ret > 0):
                #print('CAN_CH通道接收帧成功\r\n')
                #print(vci_can_obj_rx.ID)
                #print(list(vci_can_obj_rx.Data))
                #获取帧的ID号来判断CMD命令
                id = int(vci_can_obj_rx.ID)
                id_str_hex = '0x{:08x}'.format(id)
                id_bitarray = bitstring.BitArray(id_str_hex)

                #提取CMD字段
                boardinfo = id_bitarray[3:8].uint
                cmd = id_bitarray[8:16].uint
                module_id = id_bitarray[16:24].uint
                interface_id = id_bitarray[24:32].uint

                Params.timeOut_dict[boardinfo] = time.clock()



                vci_can_obj_tx.SendType = 1
                vci_can_obj_tx.DataLen = 8
                vci_can_obj_tx.ExternFlag = 1
                if cmd == 0x5A:  # 同步帧
                    #QThread.sleep(1)
                    Params.starttime = time.clock()
                    self.serialNumInfoGet()

                    #print('CAN_CH通道接收同步帧成功\r\n')
                    #每次收到同步帧后进行板号记录,并且将板号信息记录到板卡信息组中
                    Params.boardinfoGroup.append(boardinfo)
                    #发送时间帧
                    # 要发送时间帧响应,CMD=0xA5
                    vci_can_obj_tx.ID = boardinfo << 24 | 0xA5 << 16 | 0x01 << 8 | 0x01
                    #print(hex(vci_can_obj_tx.ID))
                    #获取主机当前时间,并进行数据区域组包
                    curr_time = datetime.datetime.now()
                    #print(curr_time)
                    #print(type(curr_time))
                    vci_can_obj_tx.Data[7] = 100
                    vci_can_obj_tx.Data[6] = (curr_time.year >> 8) & 0xff
                    vci_can_obj_tx.Data[5] = curr_time.year & 0xff
                    vci_can_obj_tx.Data[4] = curr_time.month & 0xff
                    vci_can_obj_tx.Data[3] = curr_time.day & 0xff
                    vci_can_obj_tx.Data[2] = curr_time.hour & 0xff
                    vci_can_obj_tx.Data[1] = curr_time.minute & 0xff
                    vci_can_obj_tx.Data[0] = curr_time.second & 0xff


                    chipid = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,0x00, 0x00, 0x00, 0x00]
                    chipbatch = Params.chipBatch & 0xffff
                    year = curr_time.year &0x3fff
                    month = curr_time.month & 0x0f
                    day = curr_time.day & 0x1f
                    hour = curr_time.hour & 0x1f
                    minute = curr_time.minute & 0x3f
                    second = curr_time.second & 0x3f
                    chipmodel = 1&0xff
                    serialnum = Params.serialNum &0xffff
                    print("serialnum: %04x" %(serialnum))
                    print(Params.chipId_dict)

                    timestamp_tmp = [second, minute, hour, day, month, year]

                    Params.board_timestamp_dict[boardinfo] = timestamp_tmp

                    chipid[0] = 0x00    #校验
                    chipid[1] = 0x00    #随机(保留)
                    chipid[2] = serialnum & 0xff    #序列号（从1开始）
                    chipid[3] = (serialnum>>8)&0xff
                    chipid[4] = chipmodel
                    chipid[5] = second|(minute&0x03)<<6
                    chipid[6] = ((minute>>2)&0x0f)|((hour&0x0f)<<4)
                    chipid[7] = ((hour>>4)&0x01)|((day&0x1f)<<1)|((month&0x03)<<6)
                    chipid[8] = ((month>>2)&0x03)|((year&0x3f)<<2)
                    chipid[9] = (year>>6)&0xff
                    chipid[10] = Params.chipBatch&0xff
                    chipid[11] = (Params.chipBatch>>8)&0xff

                    key = boardinfo
                    value = chipid
                    Params.chipId_dict[key] = value
                    print(Params.chipId_dict)



                    Params.timeOut_dict[boardinfo] = time.clock()
                    Params.boardstate_dict[boardinfo] = 1


                    #print(str(chipid))
                    #print(str(list(vci_can_obj_tx.Data)))
                    #调用驱动发送时间帧
                    ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH, byref(vci_can_obj_tx), 1)
                    if ret == STATUS_OK:
                        print('CAN_CH通道发送时间帧成功\r\n')
                    if ret != STATUS_OK:
                        print('CAN_CH通道发送时间帧失败\r\n')
                    #self.msleep(1)  # 处理器较快需要加msleep延迟，不然接收不到数据
                    #发送启动帧
                    # 要发送启动帧,CMD=0xA6
                    vci_can_obj_tx.ID = boardinfo << 24 | 0xA6 << 16 | 0x01 << 8 | 0x01

                    #7~6字节保留
                    vci_can_obj_tx.Data[7] = 0
                    vci_can_obj_tx.Data[6] = 0
                    #第5字节代表测试阶段 1:新封 2:筛选 3:考核 4:入库
                    vci_can_obj_tx.Data[5] = (Params.testStage >> 8) & 0xff
                    # 第4字节保留
                    vci_can_obj_tx.Data[4] = 0
                    #第3-2字节代表序列号
                    vci_can_obj_tx.Data[3] = (Params.serialNum>>8) & 0xff
                    vci_can_obj_tx.Data[2] = Params.serialNum & 0xff
                    # 第1-0字节代表批号
                    vci_can_obj_tx.Data[1] = Params.chipBatch & 0xff
                    vci_can_obj_tx.Data[0] = (Params.chipBatch>>8) & 0xff
                    vci_can_obj_tx.SendType = 1
                    vci_can_obj_tx.DataLen = 8
                    vci_can_obj_tx.ExternFlag = 1
                    #print(hex(vci_can_obj_tx.ID))
                    #print(list(vci_can_obj_tx.Data))
                    QThread.msleep(1)
                    # 调用驱动发送启动帧
                    ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH, byref(vci_can_obj_tx), 1)
                    if ret == STATUS_OK:
                        print('CAN_CH通道发送启动帧成功\r\n')
                    if ret != STATUS_OK:
                        print('CAN_CH通道发送启动帧失败\r\n')
                    QThread.msleep(1)

                elif cmd == 0x11:  #下位机信息帧1
                    #print('CAN_CH通道接收信息帧1成功\r\n')
                    #收到下位机信息帧1后根据boardinfo来存储芯片ID
                    #获取ID低8字节
                    for i in range(8):
                        Params.id_chip[boardinfo][i] = vci_can_obj_rx.Data[i]
                    # key = boardinfo
                    # value = Params.id_chip
                    # Params.chipId_dict[key] = value



                elif cmd == 0x12:  #下位机信息帧2
                    #print('CAN_CH通道接收信息帧2成功\r\n')
                    #接收信息帧,即ID号，共两帧，此帧为ID信息帧2
                    #datatmp = list(vci_can_obj_rx.Data)
                    Params.id_chip[boardinfo][8] = vci_can_obj_rx.Data[0]
                    Params.id_chip[boardinfo][9] = vci_can_obj_rx.Data[1]
                    Params.id_chip[boardinfo][10] = vci_can_obj_rx.Data[2]
                    Params.id_chip[boardinfo][11] = vci_can_obj_rx.Data[3]
                    key = boardinfo
                    value = Params.id_chip[boardinfo]
                    if(Params.chipId_dict[key] != value):
                        print("(Params.chipId_dict[key] != value)")
                        Params.chipId_dict[key] = value
                        # 添加数据库中的相关字段，包括(chip_id, jobnum, batchnum, stage, state, boardnum, modue_interface, module_interface_fuction)
                    module_interface_dict = dict()
                    module_interface_fuction = dict()
                    Params.timeStart_dict[boardinfo] = time.clock()
                    trdb.addData(json.dumps(Params.chipId_dict[boardinfo]), Params.jobNum, Params.chipBatch, Params.testStage, 2,
                                 boardinfo, module_interface_dict, module_interface_fuction, Params.board_timestamp_dict[boardinfo])

                    # boardnum chipid 进度 状态 开始时间 耗时
                    # tbvcontentsignal = pyqtSignal(int, str, int, str, str, int)

                    currenttime = time.time()
                    timehead = time.strftime('%H:%M:%S', time.localtime(currenttime))
                    timesecs = (currenttime - int(currenttime)) * 1000
                    timestamp = "%s.%03d" % (timehead, timesecs)
                    self.tbvcontentsignal.emit(boardinfo, str(Params.chipId_dict[boardinfo]), 0, "测试中", timestamp, 0)

                elif cmd == 0x31:  #接口状态帧
                    #print('CAN_CH通道接收接口状态帧成功\r\n')
                    #module_id/interface_id

                    interface_dict = dict()
                    '''
                    {
                        "模块1":{"接口1":1, "接口2":1},
                        "模块2":{"接口1":1, "接口2":1}
                    }
                    
                    
                    '''
                    #print(Params.chipId_dict[boardinfo])

                    print(Params.board_timestamp_dict[boardinfo])
                    data = trdb.getData(Params.chipId_dict[boardinfo], Params.board_timestamp_dict[boardinfo])
                    print(data)

                    #QThread.sleep(100)
                    #print(data)
                    datajson = json.dumps(data, ensure_ascii=False)
                    datalist = json.loads(datajson)

                    module_interface_dict = eval(datalist[0][7])
                    module_interface_fuction = eval(datalist[0][8])
                    #print(module_interface_dict)
                    #print(module_interface_fuction)

                    interface_id = interface_id + 1
                    #print("interfaceid is %d " %(interface_id) )
                    for i in range(interface_id):
                        count = i // 8
                        bit = i % 8
                        interface_dict[str(i)] = (vci_can_obj_rx.Data[count] >> bit)&0x01
                    module_interface_dict[str(module_id)] = interface_dict
                    timeconsume = time.clock() - Params.timeStart_dict[boardinfo]
                    trdb.editData(Params.chipId_dict[boardinfo], Params.jobNum, Params.chipBatch, Params.testStage, 2, boardinfo, module_interface_dict,
                             module_interface_fuction, Params.board_timestamp_dict[boardinfo])

                    # while True:
                    #     QThread.sleep(100)
                    # boardnum chipid 进度 状态 开始时间 耗时
                    #tbvcontentsignal = pyqtSignal(int, str, int, str, str, int)

                    interface_id_sum = self.interfaceCurrentSum(module_interface_dict)

                    self.tbvcontentsignal.emit(boardinfo, str(Params.chipId_dict[boardinfo]), interface_id_sum, "测试中",
                                               '', float('%04f' % timeconsume))

                    #QThread.msleep(1500)

                elif cmd == 0x32:  #功能状态帧
                    fuction_dict = dict()
                    interface_dict = dict()
                    fuction_id = vci_can_obj_rx.Data[7]
                    print('CAN_CH通道接收功能状态帧成功\r\n')
                    data = trdb.getData(Params.chipId_dict[boardinfo], Params.board_timestamp_dict[boardinfo])
                    datajson = json.dumps(data, ensure_ascii=False)
                    datalist = json.loads(datajson)
                    #print(datalist)
                    module_interface_dict = eval(datalist[0][7])
                    module_interface_fuction = eval(datalist[0][8])
                    # print("debug2222")
                    # print(module_interface_dict)
                    # print(module_interface_fuction)

                    for i in range(64):
                        count = i // 8
                        bit = i % 8
                        fuction_dict[i] = (vci_can_obj_rx.Data[count] >> bit)&0x01
                    interface_dict = copy.deepcopy(module_interface_dict[str(module_id)])
                    interface_dict[str(interface_id)] = fuction_dict
                    module_interface_fuction[str(module_id)] = interface_dict
                    trdb.editData(Params.chipId_dict[boardinfo], Params.jobNum, Params.chipBatch, Params.testStage, 2,
                                  boardinfo, module_interface_dict,
                                  module_interface_fuction,Params.board_timestamp_dict[boardinfo])
                    # while True:
                    #     QThread.sleep(100)
                elif cmd == 0x77:  #测试结束帧,更新状态
                    print('CAN_CH通道接收结束帧成功\r\n')
                    Params.boardstate_dict[boardinfo] = 2
                    data = trdb.getData(Params.chipId_dict[boardinfo],Params.board_timestamp_dict[boardinfo])
                    datajson = json.dumps(data, ensure_ascii=False)
                    datalist = json.loads(datajson)
                    module_interface_dict = eval(datalist[0][7])
                    module_interface_fuction = eval(datalist[0][8])
                    state = vci_can_obj_rx.Data[0]

                    trdb.editData(Params.chipId_dict[boardinfo], Params.jobNum, Params.chipBatch, Params.testStage, state,
                                  boardinfo, module_interface_dict,
                                  module_interface_fuction,Params.board_timestamp_dict[boardinfo])

                    Params.endtime = time.clock()
                    print('Running time: %s Seconds' % (Params.endtime - Params.starttime))
                    timeconsume = time.clock() - Params.timeStart_dict[boardinfo]
                    print(time.clock())
                    print(Params.timeStart_dict[boardinfo])
                    if state == 0:
                        self.tbvcontentsignal.emit(boardinfo, str(Params.chipId_dict[boardinfo]), -1, "测试失败",
                                               '', float('%04f' % timeconsume))
                    elif state == 1:
                        self.tbvcontentsignal.emit(boardinfo, str(Params.chipId_dict[boardinfo]), -1, "测试成功",
                                               '', float('%04f' % timeconsume))

                    del (Params.timeOut_dict[boardinfo])
                    del (Params.timeStart_dict[boardinfo])
                    del (Params.chipId_dict[boardinfo])
                    del (Params.boardstate_dict[boardinfo])
                    del (Params.board_timestamp_dict[boardinfo])
                    Params.id_chip[boardinfo].clear()

            #################################END#################################

    def interfaceCurrentSum(self, moduleInterfaceDict):
        interface_sum = 0
        for i in moduleInterfaceDict:
            if isinstance(moduleInterfaceDict[i], dict):
                for j in moduleInterfaceDict[i]:
                    interface_sum = interface_sum + 1
        return  interface_sum

    def serialNumInfoGet(self):
        tr_serial_path = os.getcwd() + '/trdb/{}/'.format(Params.chipBatch)
        file = tr_serial_path + "serialnum.txt"
        serialfile = open(file, encoding='utf-8', mode='r')

        with serialfile:
            line = serialfile.readline()
            if line:
                serialconfig = line.split(' ')
                Params.serialNum = int(serialconfig[2])
        serialfile.close()

        serialfile1 = open(file, encoding='utf-8', mode='w')
        with serialfile1:
            serialconfig1 = 'SERIAL_CONFIG_COUNT = ' + str(Params.serialNum + 1)
            serialfile1.write(serialconfig1)
        serialfile1.close()

    def itemInfoGet(self):


        Params._item_info = None
        with open("./xinfeng_info.json", "r", encoding='utf-8') as fd:
            Params._item_info = json.load(fd)
        if Params._item_info == None:
            print("xinfeng_info no exist!")
            return
        # print(Params._item_info)

        Params.interfacesum = 0
        Params.functionsum = 0
        print(list(Params._item_info.keys()))
        for i in Params._item_info:
            if isinstance(Params._item_info[i], dict):
                for j in Params._item_info[i]:
                    if isinstance(Params._item_info[i][j], dict):
                        for k in Params._item_info[i][j]:
                            if isinstance(Params._item_info[i][j][k], dict):
                                for m in Params._item_info[i][j][k]:
                                    Params.interfacesum = Params.interfacesum + 1
                                    if isinstance(Params._item_info[i][j][k][m], dict):
                                        for n in Params._item_info[i][j][k][m]:
                                            # print(Params._item_info[i][j][k][m][n])
                                            Params.functionsum = Params.functionsum + 1
        print(Params.interfacesum)
        print(Params.functionsum)
        #self.ui.pgbar.setRange(0, 80)
        for i in range(32):
            Params.pgbar[i].setRange(0, 80)

#测试用
class MyThread_Trans(QThread):
    def __init__(self, ui):
        super().__init__()
        self.ui = ui
    def run(self):
        # 通道1发送数据
        # ubyte_array = c_ubyte * 8
        # a = ubyte_array(1, 2, 3, 4, 5, 6, 7, 8)
        # ubyte_3array = c_ubyte * 3
        # b = ubyte_3array(0, 0, 0)

        #vci_can_obj = VCI_CAN_OBJ(0x1, 0, 0, 1, 0, 0, 8, a, b)  # 单次发送
        tx_vci_can_obj = VCI_CAN_OBJ()
        rx_vci_can_obj = VCI_CAN_OBJ()
        #发送同步帧
        board_id = 0x12
        cmd = 0x5A
        tx_vci_can_obj.ID = (board_id<<24 | cmd<<16)&0xffffffff
        tx_vci_can_obj.Data[0] = 0x01
        tx_vci_can_obj.Data[1] = 0x00
        tx_vci_can_obj.Data[2] = 0x00
        tx_vci_can_obj.Data[3] = 0x00
        tx_vci_can_obj.Data[4] = 0x00
        tx_vci_can_obj.Data[5] = 0x00
        tx_vci_can_obj.Data[6] = 0x00
        tx_vci_can_obj.Data[7] = 0x00
        tx_vci_can_obj.SendType = 1
        tx_vci_can_obj.DataLen = 8
        tx_vci_can_obj.ExternFlag = 1
        #print(tx_vci_can_obj.ID)
        #print(list(tx_vci_can_obj.Data))
        #QThread.msleep(10)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        if ret == STATUS_OK:
            print('CAN_CH_TEST通道发送同步帧成功\r\n')
        if ret != STATUS_OK:
            print('CAN_CH_TEST通道发送同步帧失败\r\n')

        time_recv = []
        while True:
            QThread.msleep(1)
            ret = canDLL.VCI_Receive(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(rx_vci_can_obj), 1, 0)
            if ret > 0:  # 接收到一帧数据
                #print(rx_vci_can_obj.ID)
                #print(list(rx_vci_can_obj.Data))
                if ((rx_vci_can_obj.ID >>24)&0x1f) == 0x12 and ((rx_vci_can_obj.ID >>16)&0xff) == 0xA5: #boardid一致
                    #print('CAN_CH_TEST通道接收时间帧成功\r\n')
                    for i in range(0, 8):
                        time_recv.append(rx_vci_can_obj.Data[i])
                    break
        while True:
            QThread.msleep(1)
            ret = canDLL.VCI_Receive(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(rx_vci_can_obj), 1, 0)
            if ret > 0:  # 接收到一帧数据
                #print(rx_vci_can_obj.ID)
                #print(list(rx_vci_can_obj.Data))
                if ((rx_vci_can_obj.ID >>24)&0x1f) == 0x12 and ((rx_vci_can_obj.ID >>16)&0xff) == 0xA6: #boardid一致
                    #print('CAN_CH_TEST通道接收启动帧成功\r\n')
                    testStage = rx_vci_can_obj.Data[5]  #测试阶段获取
                    serialNum = rx_vci_can_obj.Data[3]<<8|rx_vci_can_obj.Data[2]
                    chipBatch = rx_vci_can_obj.Data[1]<<8|rx_vci_can_obj.Data[0]
                    break
        chipid = [0 for i in range(12)]
        #组装CHIPID
        chipid[0] = 0x00  # 校验
        chipid[1] = 0x00  # 随机(保留)
        chipid[2] = serialNum & 0xff  # 序列号（从1开始）
        chipid[3] = (serialNum >> 8) & 0xff
        chipid[4] = 0x01
        chipid[5] = time_recv[0] | (time_recv[1] & 0x03) << 6
        chipid[6] = ((time_recv[1] >> 2) & 0x0f) | ((time_recv[2] & 0x0f) << 4)
        chipid[7] = ((time_recv[2] >> 4) & 0x01) | ((time_recv[3] & 0x1f) << 1) | ((time_recv[4]  & 0x03) << 6)
        chipid[8] = ((time_recv[4] >> 2) & 0x03) | ((time_recv[5] & 0x3f) << 2)
        chipid[9] = (time_recv[5] >> 6) & 0x03 | (time_recv[6]&0x3f) << 2
        chipid[10] = Params.chipBatch & 0xff
        chipid[11] = (Params.chipBatch >> 8) & 0xff
        #发送信息帧1
        board_id = 0x12
        cmd = 0x11
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16) & 0xffffffff
        tx_vci_can_obj.Data[0] = chipid[0]
        tx_vci_can_obj.Data[1] = chipid[1]
        tx_vci_can_obj.Data[2] = chipid[2]
        tx_vci_can_obj.Data[3] = chipid[3]
        tx_vci_can_obj.Data[4] = chipid[4]
        tx_vci_can_obj.Data[5] = chipid[5]
        tx_vci_can_obj.Data[6] = chipid[6]
        tx_vci_can_obj.Data[7] = chipid[7]
        tx_vci_can_obj.SendType = 1
        tx_vci_can_obj.DataLen = 8
        tx_vci_can_obj.ExternFlag = 1
        QThread.msleep(1)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送信息帧1成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送信息帧1失败\r\n')

        # 发送信息帧2
        board_id = 0x12
        cmd = 0x12
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16) & 0xffffffff
        tx_vci_can_obj.Data[0] = chipid[8]
        tx_vci_can_obj.Data[1] = chipid[9]
        tx_vci_can_obj.Data[2] = chipid[10]
        tx_vci_can_obj.Data[3] = chipid[11]
        tx_vci_can_obj.Data[4] = 0x00
        tx_vci_can_obj.Data[5] = 0x00
        tx_vci_can_obj.Data[6] = 0x00
        tx_vci_can_obj.Data[7] = 0x00
        QThread.msleep(1)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送信息帧2成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送信息帧2失败\r\n')

        #发送接口状态帧
        board_id = 0x12
        cmd = 0x31
        module_id = 0x23
        interface_id = 0x0f
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16 |module_id << 8|interface_id) & 0xffffffff
        tx_vci_can_obj.Data[0] = 0xff
        tx_vci_can_obj.Data[1] = 0xff
        tx_vci_can_obj.Data[2] = 0x00
        tx_vci_can_obj.Data[3] = 0x00
        tx_vci_can_obj.Data[4] = 0x00
        tx_vci_can_obj.Data[5] = 0x00
        tx_vci_can_obj.Data[6] = 0x00
        tx_vci_can_obj.Data[7] = 0x00
        QThread.msleep(1)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送接口状态帧1成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送接口状态帧1失败\r\n')

        # 发送功能状态帧
        board_id = 0x12
        cmd = 0x32
        module_id = 0x23
        interface_id = 0x01
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16 | module_id << 8 | interface_id) & 0xffffffff
        tx_vci_can_obj.Data[0] = 0x00
        tx_vci_can_obj.Data[1] = 0x00
        tx_vci_can_obj.Data[2] = 0x00
        tx_vci_can_obj.Data[3] = 0x00
        tx_vci_can_obj.Data[4] = 0x00
        tx_vci_can_obj.Data[5] = 0x00
        tx_vci_can_obj.Data[6] = 0xff
        tx_vci_can_obj.Data[7] = 0xff
        QThread.msleep(1)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送功能状态帧成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送功能状态帧失败\r\n')

        # 发送接口状态帧
        board_id = 0x12
        cmd = 0x31
        module_id = 0x21
        interface_id = 0x3f
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16 | module_id << 8 | interface_id) & 0xffffffff
        tx_vci_can_obj.Data[0] = 0xff
        tx_vci_can_obj.Data[1] = 0xff
        tx_vci_can_obj.Data[2] = 0xff
        tx_vci_can_obj.Data[3] = 0xff
        tx_vci_can_obj.Data[4] = 0xff
        tx_vci_can_obj.Data[5] = 0xff
        tx_vci_can_obj.Data[6] = 0xff
        tx_vci_can_obj.Data[7] = 0xff
        QThread.msleep(1)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送接口状态帧2成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送接口状态帧2失败\r\n')

        # 发送结束帧
        board_id = 0x12
        cmd = 0x77
        module_id = 0x23
        interface_id = 0x01
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16 | module_id << 8 | interface_id) & 0xffffffff
        tx_vci_can_obj.Data[0] = 0x01
        tx_vci_can_obj.Data[1] = 0x00
        tx_vci_can_obj.Data[2] = 0x00
        tx_vci_can_obj.Data[3] = 0x00
        tx_vci_can_obj.Data[4] = 0x00
        tx_vci_can_obj.Data[5] = 0x00
        tx_vci_can_obj.Data[6] = 0x00
        tx_vci_can_obj.Data[7] = 0x00
        QThread.msleep(1)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送结束帧成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送结束帧失败\r\n')

        # while True:
        #     QThread.sleep(100)

        # 发送同步帧
        board_id = 0x02
        cmd = 0x5A
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16) & 0xffffffff
        tx_vci_can_obj.Data[0] = 0x01
        tx_vci_can_obj.Data[1] = 0x00
        tx_vci_can_obj.Data[2] = 0x00
        tx_vci_can_obj.Data[3] = 0x00
        tx_vci_can_obj.Data[4] = 0x00
        tx_vci_can_obj.Data[5] = 0x00
        tx_vci_can_obj.Data[6] = 0x00
        tx_vci_can_obj.Data[7] = 0x00
        tx_vci_can_obj.SendType = 1
        tx_vci_can_obj.DataLen = 8
        tx_vci_can_obj.ExternFlag = 1
        # print(tx_vci_can_obj.ID)
        # print(list(tx_vci_can_obj.Data))
        # QThread.msleep(10)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送同步帧成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送同步帧失败\r\n')

        time_recv = []
        while True:
            QThread.msleep(1)
            ret = canDLL.VCI_Receive(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(rx_vci_can_obj), 1, 0)
            if ret > 0:  # 接收到一帧数据
                # print(rx_vci_can_obj.ID)
                # print(list(rx_vci_can_obj.Data))
                if ((rx_vci_can_obj.ID >> 24) & 0x1f) == 0x02 and (
                        (rx_vci_can_obj.ID >> 16) & 0xff) == 0xA5:  # boardid一致
                    #print('CAN_CH_TEST通道接收时间帧成功\r\n')
                    for i in range(0, 8):
                        time_recv.append(rx_vci_can_obj.Data[i])
                    break
        while True:
            QThread.msleep(1)
            ret = canDLL.VCI_Receive(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(rx_vci_can_obj), 1, 0)
            if ret > 0:  # 接收到一帧数据
                # print(rx_vci_can_obj.ID)
                # print(list(rx_vci_can_obj.Data))
                if ((rx_vci_can_obj.ID >> 24) & 0x1f) == 0x02 and (
                        (rx_vci_can_obj.ID >> 16) & 0xff) == 0xA6:  # boardid一致
                    #print('CAN_CH_TEST通道接收启动帧成功\r\n')
                    testStage = rx_vci_can_obj.Data[5]  # 测试阶段获取
                    serialNum = rx_vci_can_obj.Data[3] << 8 | rx_vci_can_obj.Data[2]
                    chipBatch = rx_vci_can_obj.Data[1] << 8 | rx_vci_can_obj.Data[0]
                    break
        chipid = [0 for i in range(12)]
        # 组装CHIPID
        chipid[0] = 0x00  # 校验
        chipid[1] = 0x00  # 随机(保留)
        chipid[2] = serialNum & 0xff  # 序列号（从1开始）
        chipid[3] = (serialNum >> 8) & 0xff
        chipid[4] = 0x01
        chipid[5] = time_recv[0] | (time_recv[1] & 0x03) << 6
        chipid[6] = ((time_recv[1] >> 2) & 0x0f) | ((time_recv[2] & 0x0f) << 4)
        chipid[7] = ((time_recv[2] >> 4) & 0x01) | ((time_recv[3] & 0x1f) << 1) | ((time_recv[4] & 0x03) << 6)
        chipid[8] = ((time_recv[4] >> 2) & 0x03) | ((time_recv[5] & 0x3f) << 2)
        chipid[9] = (time_recv[5] >> 6) & 0x03 | (time_recv[6] & 0x3f) << 2
        chipid[10] = Params.chipBatch & 0xff
        chipid[11] = (Params.chipBatch >> 8) & 0xff
        # 发送信息帧1
        board_id = 0x02
        cmd = 0x11
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16) & 0xffffffff
        tx_vci_can_obj.Data[0] = chipid[0]
        tx_vci_can_obj.Data[1] = chipid[1]
        tx_vci_can_obj.Data[2] = chipid[2]
        tx_vci_can_obj.Data[3] = chipid[3]
        tx_vci_can_obj.Data[4] = chipid[4]
        tx_vci_can_obj.Data[5] = chipid[5]
        tx_vci_can_obj.Data[6] = chipid[6]
        tx_vci_can_obj.Data[7] = chipid[7]
        tx_vci_can_obj.SendType = 1
        tx_vci_can_obj.DataLen = 8
        tx_vci_can_obj.ExternFlag = 1
        QThread.msleep(1)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送信息帧1成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送信息帧1失败\r\n')

        # 发送信息帧2
        board_id = 0x02
        cmd = 0x12
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16) & 0xffffffff
        tx_vci_can_obj.Data[0] = chipid[8]
        tx_vci_can_obj.Data[1] = chipid[9]
        tx_vci_can_obj.Data[2] = chipid[10]
        tx_vci_can_obj.Data[3] = chipid[11]
        tx_vci_can_obj.Data[4] = 0x00
        tx_vci_can_obj.Data[5] = 0x00
        tx_vci_can_obj.Data[6] = 0x00
        tx_vci_can_obj.Data[7] = 0x00
        QThread.msleep(1)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送信息帧2成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送信息帧2失败\r\n')
        #QThread.sleep(5)
        # 发送接口状态帧
        board_id = 0x02
        cmd = 0x31
        module_id = 0x23
        interface_id = 0x0f
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16 | module_id << 8 | interface_id) & 0xffffffff
        tx_vci_can_obj.Data[0] = 0xff
        tx_vci_can_obj.Data[1] = 0xff
        tx_vci_can_obj.Data[2] = 0x00
        tx_vci_can_obj.Data[3] = 0x00
        tx_vci_can_obj.Data[4] = 0x00
        tx_vci_can_obj.Data[5] = 0x00
        tx_vci_can_obj.Data[6] = 0x00
        tx_vci_can_obj.Data[7] = 0x00
        QThread.msleep(1)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        #QThread.sleep(10)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送接口状态帧1成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送接口状态帧1失败\r\n')

        # 发送功能状态帧
        board_id = 0x02
        cmd = 0x32
        module_id = 0x23
        interface_id = 0x01
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16 | module_id << 8 | interface_id) & 0xffffffff
        tx_vci_can_obj.Data[0] = 0x00
        tx_vci_can_obj.Data[1] = 0x00
        tx_vci_can_obj.Data[2] = 0x00
        tx_vci_can_obj.Data[3] = 0x00
        tx_vci_can_obj.Data[4] = 0x00
        tx_vci_can_obj.Data[5] = 0x00
        tx_vci_can_obj.Data[6] = 0xff
        tx_vci_can_obj.Data[7] = 0xff
        QThread.msleep(1)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送功能状态帧成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送功能状态帧失败\r\n')



        # 发送同步帧
        board_id = 0x05
        cmd = 0x5A
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16) & 0xffffffff
        tx_vci_can_obj.Data[0] = 0x01
        tx_vci_can_obj.Data[1] = 0x00
        tx_vci_can_obj.Data[2] = 0x00
        tx_vci_can_obj.Data[3] = 0x00
        tx_vci_can_obj.Data[4] = 0x00
        tx_vci_can_obj.Data[5] = 0x00
        tx_vci_can_obj.Data[6] = 0x00
        tx_vci_can_obj.Data[7] = 0x00
        tx_vci_can_obj.SendType = 1
        tx_vci_can_obj.DataLen = 8
        tx_vci_can_obj.ExternFlag = 1
        # print(tx_vci_can_obj.ID)
        # print(list(tx_vci_can_obj.Data))
        # QThread.msleep(10)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送同步帧成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送同步帧失败\r\n')

        time_recv = []
        while True:
            QThread.msleep(1)
            ret = canDLL.VCI_Receive(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(rx_vci_can_obj), 1, 0)
            if ret > 0:  # 接收到一帧数据
                # print(rx_vci_can_obj.ID)
                # print(list(rx_vci_can_obj.Data))
                if ((rx_vci_can_obj.ID >> 24) & 0x1f) == 0x05 and (
                        (rx_vci_can_obj.ID >> 16) & 0xff) == 0xA5:  # boardid一致
                    #print('CAN_CH_TEST通道接收时间帧成功\r\n')
                    for i in range(0, 8):
                        time_recv.append(rx_vci_can_obj.Data[i])
                    break
        while True:
            QThread.msleep(1)
            ret = canDLL.VCI_Receive(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(rx_vci_can_obj), 1, 0)
            if ret > 0:  # 接收到一帧数据
                # print(rx_vci_can_obj.ID)
                # print(list(rx_vci_can_obj.Data))
                if ((rx_vci_can_obj.ID >> 24) & 0x1f) == 0x05 and (
                        (rx_vci_can_obj.ID >> 16) & 0xff) == 0xA6:  # boardid一致
                    #print('CAN_CH_TEST通道接收启动帧成功\r\n')
                    testStage = rx_vci_can_obj.Data[5]  # 测试阶段获取
                    serialNum = rx_vci_can_obj.Data[3] << 8 | rx_vci_can_obj.Data[2]
                    chipBatch = rx_vci_can_obj.Data[1] << 8 | rx_vci_can_obj.Data[0]
                    break
        chipid = [0 for i in range(12)]
        # 组装CHIPID
        chipid[0] = 0x00  # 校验
        chipid[1] = 0x00  # 随机(保留)
        chipid[2] = serialNum & 0xff  # 序列号（从1开始）
        chipid[3] = (serialNum >> 8) & 0xff
        chipid[4] = 0x01
        chipid[5] = time_recv[0] | (time_recv[1] & 0x03) << 6
        chipid[6] = ((time_recv[1] >> 2) & 0x0f) | ((time_recv[2] & 0x0f) << 4)
        chipid[7] = ((time_recv[2] >> 4) & 0x01) | ((time_recv[3] & 0x1f) << 1) | ((time_recv[4] & 0x03) << 6)
        chipid[8] = ((time_recv[4] >> 2) & 0x03) | ((time_recv[5] & 0x3f) << 2)
        chipid[9] = (time_recv[5] >> 6) & 0x03 | (time_recv[6] & 0x3f) << 2
        chipid[10] = Params.chipBatch & 0xff
        chipid[11] = (Params.chipBatch >> 8) & 0xff

        # 发送信息帧1
        board_id = 0x05
        cmd = 0x11
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16) & 0xffffffff
        tx_vci_can_obj.Data[0] = chipid[0]
        tx_vci_can_obj.Data[1] = chipid[1]
        tx_vci_can_obj.Data[2] = chipid[2]
        tx_vci_can_obj.Data[3] = chipid[3]
        tx_vci_can_obj.Data[4] = chipid[4]
        tx_vci_can_obj.Data[5] = chipid[5]
        tx_vci_can_obj.Data[6] = chipid[6]
        tx_vci_can_obj.Data[7] = chipid[7]
        tx_vci_can_obj.SendType = 1
        tx_vci_can_obj.DataLen = 8
        tx_vci_can_obj.ExternFlag = 1
        QThread.msleep(1)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送信息帧1成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送信息帧1失败\r\n')

        # 发送信息帧2
        board_id = 0x05
        cmd = 0x12
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16) & 0xffffffff
        tx_vci_can_obj.Data[0] = chipid[8]
        tx_vci_can_obj.Data[1] = chipid[9]
        tx_vci_can_obj.Data[2] = chipid[10]
        tx_vci_can_obj.Data[3] = chipid[11]
        tx_vci_can_obj.Data[4] = 0x00
        tx_vci_can_obj.Data[5] = 0x00
        tx_vci_can_obj.Data[6] = 0x00
        tx_vci_can_obj.Data[7] = 0x00
        QThread.msleep(1)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送信息帧2成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送信息帧2失败\r\n')

        # 发送接口状态帧
        board_id = 0x05
        cmd = 0x31
        module_id = 0x23
        interface_id = 0x0f
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16 | module_id << 8 | interface_id) & 0xffffffff
        tx_vci_can_obj.Data[0] = 0xff
        tx_vci_can_obj.Data[1] = 0xff
        tx_vci_can_obj.Data[2] = 0x00
        tx_vci_can_obj.Data[3] = 0x00
        tx_vci_can_obj.Data[4] = 0x00
        tx_vci_can_obj.Data[5] = 0x00
        tx_vci_can_obj.Data[6] = 0x00
        tx_vci_can_obj.Data[7] = 0x00
        QThread.msleep(1)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送接口状态帧1成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送接口状态帧1失败\r\n')

        # 发送功能状态帧
        board_id = 0x05
        cmd = 0x32
        module_id = 0x23
        interface_id = 0x01
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16 | module_id << 8 | interface_id) & 0xffffffff
        tx_vci_can_obj.Data[0] = 0x00
        tx_vci_can_obj.Data[1] = 0x00
        tx_vci_can_obj.Data[2] = 0x00
        tx_vci_can_obj.Data[3] = 0x00
        tx_vci_can_obj.Data[4] = 0x00
        tx_vci_can_obj.Data[5] = 0x00
        tx_vci_can_obj.Data[6] = 0xff
        tx_vci_can_obj.Data[7] = 0xff
        QThread.msleep(1)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送功能状态帧成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送功能状态帧失败\r\n')

        # 发送接口状态帧
        board_id = 0x05
        cmd = 0x31
        module_id = 0x21
        interface_id = 0x3f
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16 | module_id << 8 | interface_id) & 0xffffffff
        tx_vci_can_obj.Data[0] = 0xff
        tx_vci_can_obj.Data[1] = 0xff
        tx_vci_can_obj.Data[2] = 0xff
        tx_vci_can_obj.Data[3] = 0xff
        tx_vci_can_obj.Data[4] = 0xff
        tx_vci_can_obj.Data[5] = 0xff
        tx_vci_can_obj.Data[6] = 0xff
        tx_vci_can_obj.Data[7] = 0xff
        QThread.msleep(1)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送接口状态帧2成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送接口状态帧2失败\r\n')
        #QThread.sleep(5)
        # # 发送接口状态帧
        # board_id = 0x02
        # cmd = 0x31
        # module_id = 0x21
        # interface_id = 0x3f
        # tx_vci_can_obj.ID = (board_id << 24 | cmd << 16 | module_id << 8 | interface_id) & 0xffffffff
        # tx_vci_can_obj.Data[0] = 0xff
        # tx_vci_can_obj.Data[1] = 0xff
        # tx_vci_can_obj.Data[2] = 0xff
        # tx_vci_can_obj.Data[3] = 0xff
        # tx_vci_can_obj.Data[4] = 0xff
        # tx_vci_can_obj.Data[5] = 0xff
        # tx_vci_can_obj.Data[6] = 0xff
        # tx_vci_can_obj.Data[7] = 0xff
        # QThread.msleep(1)
        # ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # # if ret == STATUS_OK:
        # #     print('CAN_CH_TEST通道发送接口状态帧2成功\r\n')
        # # if ret != STATUS_OK:
        # #     print('CAN_CH_TEST通道发送接口状态帧2失败\r\n')
        #
        # # 发送结束帧
        # board_id = 0x02
        # cmd = 0x77
        # module_id = 0x23
        # interface_id = 0x01
        # tx_vci_can_obj.ID = (board_id << 24 | cmd << 16 | module_id << 8 | interface_id) & 0xffffffff
        # tx_vci_can_obj.Data[0] = 0x01
        # tx_vci_can_obj.Data[1] = 0x00
        # tx_vci_can_obj.Data[2] = 0x00
        # tx_vci_can_obj.Data[3] = 0x00
        # tx_vci_can_obj.Data[4] = 0x00
        # tx_vci_can_obj.Data[5] = 0x00
        # tx_vci_can_obj.Data[6] = 0x00
        # tx_vci_can_obj.Data[7] = 0x00
        # QThread.msleep(1)
        # ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # # if ret == STATUS_OK:
        # #     print('CAN_CH_TEST通道发送结束帧成功\r\n')
        # # if ret != STATUS_OK:
        # #     print('CAN_CH_TEST通道发送结束帧失败\r\n')


        # 发送结束帧
        board_id = 0x05
        cmd = 0x77
        module_id = 0x23
        interface_id = 0x01
        tx_vci_can_obj.ID = (board_id << 24 | cmd << 16 | module_id << 8 | interface_id) & 0xffffffff
        tx_vci_can_obj.Data[0] = 0x01
        tx_vci_can_obj.Data[1] = 0x00
        tx_vci_can_obj.Data[2] = 0x00
        tx_vci_can_obj.Data[3] = 0x00
        tx_vci_can_obj.Data[4] = 0x00
        tx_vci_can_obj.Data[5] = 0x00
        tx_vci_can_obj.Data[6] = 0x00
        tx_vci_can_obj.Data[7] = 0x00
        QThread.msleep(1)
        ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, Params.CAN_CH_TEST, byref(tx_vci_can_obj), 1)
        # if ret == STATUS_OK:
        #     print('CAN_CH_TEST通道发送结束帧成功\r\n')
        # if ret != STATUS_OK:
        #     print('CAN_CH_TEST通道发送结束帧失败\r\n')



class MyThread_Recv(QThread):
    tbvcontentsignal1 = pyqtSignal(int, int, str)
    #progressBarValue = pyqtSignal(int)  # 更新进度条
    #msgsignal = pyqtSignal(str, str)
    def __init__(self, ui):
        super().__init__()
        self.ui = ui
    def run(self):
        # self.msgsignal.emit('info','数据开始传输......')
        # self.msleep(5)
        # self.progressBarValue.emit(2)  # 发送进度条的值信号

        # 初始通道
        vci_initconfig = VCI_INIT_CONFIG(0x80000008, 0xFFFFFFFF, 0,
                                         0, 0x03, 0x1C, 0)  # 波特率125k，正常模式
        ret = canDLL.VCI_InitCAN(VCI_USBCAN2, 0, 1, byref(vci_initconfig))
        if ret == STATUS_OK:
            print('调用 VCI_InitCAN2 成功\r\n')
        if ret != STATUS_OK:
            print('调用 VCI_InitCAN2 出错\r\n')

        ret = canDLL.VCI_StartCAN(VCI_USBCAN2, 0, 1)
        if ret == STATUS_OK:
            print('调用 VCI_StartCAN2 成功\r\n')
        if ret != STATUS_OK:
            print('调用 VCI_StartCAN2 出错\r\n')

        rx_vci_can_obj = VCI_CAN_OBJ_ARRAY(2500)  # 结构体数组
        while True:  # 如果没有接收到数据，一直循环查询接收。
            self.msleep(5)
            ret = canDLL.VCI_Receive(VCI_USBCAN2, 0, 1, byref(rx_vci_can_obj.ADDR), 1, 0)
            if ret > 0:  # 接收到一帧数据
                print('CAN2通道接收成功\r\n')
                print('ID：')
                print(rx_vci_can_obj.STRUCT_ARRAY[0].ID)
                print('DataLen：')
                print(rx_vci_can_obj.STRUCT_ARRAY[0].DataLen)
                print('Data：')
                print(rx_vci_can_obj.STRUCT_ARRAY[0].Data)
                self.data_handle(rx_vci_can_obj.STRUCT_ARRAY[0])

    def data_handle(self, datastruct):
        print(type(datastruct.ID))
        print(type(datastruct.DataLen))

        tmp = list(datastruct.Data)
        seq4 = []
        for i in range(len(tmp)):
            seq4.append(str(tmp[i]))
        print(' '.join(seq4))  # 1*2*3

        resulthex = []
        for i in range(0, 8):
            resulthex.append(format(list(datastruct.Data)[i], "02x"))
        print(resulthex)

        print(' '.join(resulthex))  # 1*2*3
        self.tbvcontentsignal.emit(int(datastruct.ID), int(datastruct.DataLen), ' '.join(resulthex))




