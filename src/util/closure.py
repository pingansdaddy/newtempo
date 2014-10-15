#coding:utf-8
import time


def id_generator(start=-1):
    """
    Growing in life cycle     
    @returns integer
    """
    if start < 0:
        start = int(time.time())
    count = [start]
    def incr():
        count[0] += 1
        return count[0] 
    return incr
        
