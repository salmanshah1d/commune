

from typing import Tuple, List, Union
import asyncio
from functools import partial
import commune as c
import aiohttp
import json


from aiohttp.streams import StreamReader




class VirtualClient:
    def __init__(self, module: str ='ReactAgentModule'):
        if isinstance(module, str):
            import commune
            self.module_client = c.connect(module)
            self.loop = self.module_client.loop
            self.success = self.module_client.success
        else:
            self.module_client = module
    
    def remote_call(self, remote_fn: str, *args, return_future= False, timeout:int=10, **kwargs):
        future =  asyncio.wait_for(self.module_client.async_forward(fn=remote_fn, args=args, kwargs=kwargs), timeout=timeout)
        if return_future:
            return future
        else:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(future)
            
    def __str__(self):
        return f'<VirtualClient(name={self.module_client.name}, address={self.module_client.address})>'

    def __repr__(self):
        return self.__str__()
        
    protected_attributes = [ 'module_client', 'remote_call']
    def __getattr__(self, key):

        if key in self.protected_attributes :
            return getattr(self, key)
        else:
            return lambda *args, **kwargs : partial(self.remote_call, (key))( *args, **kwargs)


# Define a custom StreamReader with a higher limit
class CustomStreamReader(StreamReader):
    def __init__(self, *args, **kwargs):
        # You can adjust the limit here to a value that fits your needs
        # This example sets it to 1MB
        super().__init__(*args, limit=1024*1024, **kwargs)


class Client(c.Module):

    def __init__( 
            self,
            ip: str ='0.0.0.0',
            port: int = 50053 ,
            network: bool = None,
            key : str = None,
            save_history: bool = True,
            history_path : str = 'history',
            loop: 'asyncio.EventLoop' = None, 
            debug: bool = False,
            serializer= 'serializer',
            **kwargs
        ):
        self.loop = c.get_event_loop() if loop == None else loop
        self.set_client(ip =ip,port = port)
        self.serializer = c.module(serializer)()
        self.key = key or c.get_key(key)
        self.my_ip = c.ip()
        self.network = c.resolve_network(network)
        self.start_timestamp = c.timestamp()
        self.save_history = save_history
        self.history_path = history_path
        self.debug = debug

        

    
    def age(self):
        return  self.start_timestamp - c.timestamp()

    def set_client(self,
            ip: str =None,
            port: int = None ,
            verbose: bool = False
            ):
        self.ip = ip if ip else c.default_ip
        self.port = port if port else c.free_port() 
        if verbose:
            c.print(f"Connecting to {self.ip}:{self.port}", color='green')
        self.address = f"{self.ip}:{self.port}"
       

    def resolve_client(self, ip: str = None, port: int = None) -> None:
        if ip != None or port != None:
            self.set_client(ip =ip,port = port)
    


    async def async_forward(self,
        fn: str,
        args: list = None,
        kwargs: dict = None,
        ip: str = None,
        port : int= None,
        timeout: int = 10,
        generator: bool = False,
        headers : dict ={'Content-Type': 'application/json'},
        ):
        self.resolve_client(ip=ip, port=port)
        args = args if args else []
        kwargs = kwargs if kwargs else {}
        url = f"http://{self.address}/{fn}/"
        input =  { 
                        "args": args,
                        "kwargs": kwargs,
                        "ip": self.my_ip,
                        "timestamp": c.timestamp(),
                        }
        # serialize this into a json string
        request = self.serializer.serialize(input)
        request = self.key.sign(request, return_json=True)

        
        
        # start a client session and send the request
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=request, headers=headers) as response:
                if response.content_type == 'text/event-stream':
                    STREAM_PREFIX = 'data: '
                    BYTES_PER_MB = 1e6
                    if self.debug:
                        progress_bar = c.tqdm(desc='MB per Second', position=0)

                    result = []
                    
                    async for line in response.content:
                        event_data = line.decode('utf-8')
                        
                        event_bytes  = len(event_data)
                        if self.debug :
                            progress_bar.update(event_bytes/(BYTES_PER_MB))
                        # remove the "data: " prefix
                        if event_data.startswith(STREAM_PREFIX):
                            event_data = event_data[len(STREAM_PREFIX):]

                        event_data = event_data.strip()
                        
                        # skip empty lines
                        if event_data == "":
                            continue

                        # if the data is formatted as a json string, load it {data: ...}
                        if isinstance(event_data, bytes):
                            event_data = event_data.decode('utf-8')

                        # if the data is formatted as a json string, load it {data: ...}
                        if isinstance(event_data, str):
                            if event_data.startswith('{') and event_data.endswith('}') and 'data' in event_data:
                                event_data = json.loads(event_data)['data']

                            result += [event_data]
                        
                    # process the result if its a json string
                    if result.startswith('{') and result.endswith('}') or \
                        result.startswith('[') and result.endswith(']'):
                        result = ''.join(result)
                        result = json.loads(result)

                elif response.content_type == 'application/json':
                    # PROCESS JSON EVENTS
                    result = await asyncio.wait_for(response.json(), timeout=timeout)
                elif response.content_type == 'text/plain':
                    # PROCESS TEXT EVENTS
                    result = await asyncio.wait_for(response.text(), timeout=timeout)
                else:
                    raise ValueError(f"Invalid response content type: {response.content_type}")
        if isinstance(result, dict):
            result = self.serializer.deserialize(result)
        elif isinstance(result, str):
            result = self.serializer.deserialize(result)
        if isinstance(result, dict) and 'data' in result:
            result = result['data']
        if self.save_history:
            input['fn'] = fn
            input['result'] = result
            input['module']  = self.address
            input['latency'] =  c.time() - input['timestamp']
            self.add_history( input)
          
        return result
    

    def process_output(self, result):
        ## handles 
        if isinstance(result, str):
            result = json.loads(result)
        if 'data' in result:
            result = self.serializer.deserialize(result)
            return result['data']
        else:
            return result
        
    def forward(self,*args,return_future:bool=False, timeout:str=4, **kwargs):
        forward_future = asyncio.wait_for(self.async_forward(*args, **kwargs), timeout=timeout)
        if return_future:
            return forward_future
        else:
            return self.loop.run_until_complete(forward_future)
        
        
    __call__ = forward

    def __str__ ( self ):
        return "Client({})".format(self.address) 
    def __repr__ ( self ):
        return self.__str__()
    def __exit__ ( self ):
        self.__del__()


    def virtual(self):
        return c.virtual_client(module = self)
    
    def __repr__(self) -> str:
        return super().__repr__()

    # HISTORY

    def add_history(self, item:dict,  key=None):

        path = self.history_path+'/' + self.key.ss58_address + '/' + str(item['timestamp'])
        return self.put(path, item)
    
    @classmethod
    def history_paths(cls, key=None, history_path='history'):
        key = c.get_key(key)
        return cls.ls(history_path + '/' + key.ss58_address)

    def history(self, key=None, history_path='history', features=['module', 'fn', 'seconds_ago', 'latency']):
        key = c.get_key(key)
        history_path = self.history_paths(key=key, history_path=history_path)
        df =  c.df([self.get(path) for path in history_path])
        now = c.timestamp()
        df['seconds_ago'] = df['timestamp'].apply(lambda x: now - x)
        df = df[features]
        return df
        
    
    @classmethod
    def all_history(cls, key=None, history_path='history'):
        key = c.get_key(key)
        return cls.glob(history_path)
        
    @classmethod
    def rm_key_history(cls, key=None, history_path='history'):
        key = c.get_key(key)
        return cls.rm(history_path + '/' + key.ss58_address)
    
    @classmethod
    def rm_history(cls, key=None, history_path='history'):
        key = c.get_key(key)
        return cls.rm(history_path)
    
    def virtual(self):
        return VirtualClient(module = self)

