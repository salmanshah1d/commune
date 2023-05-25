""" Manages a pool of grpc connections as clients
"""

import math
from typing import Tuple, List, Union
from threading import Lock
import streamlit as st
import asyncio
from loguru import logger
import concurrent
import commune
from concurrent.futures import ThreadPoolExecutor
import commune
import asyncio

class ModulePool (commune.Module):
    """ Manages a pool of grpc connections as clients
    """
    

    
    def __init__(
        self, 
        modules = None,
        max_clients:int = 20,
        
    ):
        self.max_clients = max_clients
        self.add_modules(modules)
        
        self.cull_mutex = Lock()
        self.total_requests = 0
        
        
    def add_module(self, *args, **kwargs)-> str:
        loop = self.get_event_loop()
        return loop.run_until_complete(self.async_add_module( *args, **kwargs))
        
    async def async_add_module(self, module:str = None, timeout=3)-> str:
        if not hasattr(self, 'modules'):
            self.modules = {}
        self.modules[module] = await commune.async_connect(module, timeout=timeout)
        return module
    
    
    def add_modules(self, modules:list):
        if modules == None:
            modules = commune.modules()
            
        return asyncio.gather(*[self.async_add_module(m) for m in modules])
          
        
    
    def has_module(self, module:str)->bool:
        return bool(module in self.modules)
    
    def get_module(self, module:str):
        if not self.has_module(module):
            self.add_module(module)
        return self.modules[module]

    async def async_get_module( self, 
                               module = None,
                               timeout=1, 
                               retrials=2) -> 'commune.Client':
        
        if module not in self.moddules :
            self.async_add_module(module)
            
        return self.module[ module ]
        
    

    def __str__(self):
        return "ModulePool({},{})".format(len(self.clients), self.max_)

    def __repr__(self):
        return self.__str__()
    
    def __exit__(self):
        for client in self.clients:
            client.__del__()

    def forward (
            self, 
            fn:str,
            args:list = None,
            kwargs:dict = None, 
            modules:list = None,
            min_successes: int = None,
        )  :

        loop = self.get_event_loop()
        return loop.run_until_complete (self.async_forward(kwargs=kwargs) )



    async def async_forward (
            self, 
            fn:str,
            args:list = None,
            kwargs:dict = None, 
            modules:list = None,
            timeout: int = 2,
            min_successes: int = 2,
        ) :
        # Init clients.
        
    
    
        client = await self.async_get_module( module )


        kwargs = {} if kwargs == None else kwargs
        args = [] if args == None else args

        # Make calls.
        running_tasks = []
        for index, (client) in enumerate(clients.items()):
            args, kwargs = self.copy(args), self.copy(kwargs)
            task = asyncio.create_task(
                client.async_forward(*args, **kwargs)
            )
            running_tasks.append(task)


        outputs = []
        
        while len(running_tasks) > 0:
            
            finished_tasks, running_tasks  = await asyncio.wait( running_tasks , return_when=asyncio.FIRST_COMPLETED)
            finished_tasks, running_tasks = list(finished_tasks), list(running_tasks)

            responses = await asyncio.gather(*finished_tasks)

            for response in responses:
                if  min_successes > 0:
                    if  response[1][0] == 1:
                        outputs.append( response )
                    if len(outputs) >= min_successes :
                        # cancel the rest of the tasks
                        [t.cancel() for t in running_tasks]
                        running_tasks = [t for t in running_tasks if t.cancelled()]
                        assert len(running_tasks) == 0, f'{len(running_tasks)}'
                        break
                else:
                    
                    outputs.append( response)

        return outputs

    @classmethod
    def test(cls, **kwargs):
        return cls(modules='module')
    
    
if __name__ == '__main__':
    ModulePool.run()