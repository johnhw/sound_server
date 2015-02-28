import yaml, simpleOSC, time, logging, sys
import multiprocessing
import sound_server



# simple sound test; loads a yaml file with a sequence of OSC messsages, and
# starts a sound_server instance an another process, sending each message to
# the server

logging.basicConfig(level=logging.DEBUG, format='%(message)s')
clock = sound_server.WallTimer()

if __name__=="__main__":    
   
    yml = sys.argv[1]
    with open(yml) as f:
        config = yaml.load(f)
  
    # launch a sound_server instance
    server_config = config.get("config")    
    logging.debug("Launching sound server")
    multiprocessing.Process(target=sound_server.launch, args=(server_config,)).start()
    time.sleep(2)
    
    port = config.get("port", 8000)
    # init OSC
    ip_address = config.get("ip_address", "127.0.0.1")    
    simpleOSC.initOSCClient(ip=ip_address, port=port)
    start_time = clock.time()
    next_time = start_time 
    index = 0
    
    oscs = config['osc']       
    
    # send the messages in sequence
    while index < len(oscs):
        now = clock.time()
         
        while now>=next_time:            
            osc = oscs[index]
            t, addr = osc[0], osc[1]            
            data = osc[2:]
            logging.debug("%.2f: Sending OSC message %s %s" % (now-start_time, addr, data))            
            simpleOSC.sendOSCMsg(addr, data)            
            index += 1            
            if index<len(oscs):
                next_time = now + oscs[index][0]
                
        time.sleep(0.01)
        
    