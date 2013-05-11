# Copyright (c) 2013 Alan McIntyre

import datetime
import threading
import time
import traceback

import btceapi
from btceapi.common import validatePair

from trader import TraderBase

def _runBot(bot):
    while bot.running:
        loop_start = time.time()
        
        # Collect the set of pairs for which we should get depth.
        depthPairs = set()
        for handler, pairs in bot.depthHandlers:
            depthPairs.update(pairs)
            
        depths = {}
        for p in depthPairs:
            try:
                asks, bids = btceapi.getDepth(p)
                depths[p] = (datetime.datetime.now(), asks, bids)
            except:
                bot.onDepthRetrievalError(p, traceback.format_exc())

        for p, (t, asks, bids) in depths.items():
            for handler, pairs in bot.depthHandlers:
                if p in pairs:
                    try:
                        handler(t, p, asks, bids)
                    except:
                        bot.onDepthHandlingError(p, handler, traceback.format_exc())
                    
        # Collect the set of pairs for which we should get trade history.
        tradeHistoryPairs = set()
        for handler, pairs in bot.tradeHistoryHandlers:
            tradeHistoryPairs.update(pairs)
        
        tradeHistories = {}
        for p in tradeHistoryPairs:
            try:
                trades = btceapi.getTradeHistory(p)
                tradeHistories[p] = (datetime.datetime.now(), trades)
            except:
                bot.onTradeHistoryRetrievalError(p, traceback.format_exc())
                
        for p, (t, trades) in tradeHistories.items():
            # Merge new trades into the bot's history.
            bot.mergeTradeHistory(p, trades)
            
            # Provide full history to traders
            for handler, pairs in bot.tradeHistoryHandlers:
                if p in pairs:
                    try:
                        handler(t, p, bot.tradeHistoryItems[p])
                    except:
                        bot.onTradeHistoryHandlingError(p, handler, traceback.format_exc())
                        
        # Tell all bots that have requested it that we're at the end
        # of an update loop.
        for handler in bot.loopEndHandlers:
            try:
                handler(datetime.datetime.now())
            except:
                t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                print "%s Error while calling loop end handler (%r): %s" % (t, handler, traceback.format_exc())
                
        while bot.running and time.time() - loop_start < bot.collectionInterval:
            time.sleep(0.5)

    # Give traders and opportunity to do thread-specific cleanup.
    for t in bot.traders:
        t.onExit()
    
            
class Bot(object):
    def __init__(self, bufferSpanMinutes=10):
        self.bufferSpanMinutes = bufferSpanMinutes
        self.depthHandlers = []
        self.tradeHistoryHandlers = []
        self.loopEndHandlers = []
        self.collectionInterval = 60.0
        self.running = False
        self.traders = set()
        
        self.tradeHistoryIds = {}
        self.tradeHistoryItems = {}
        
        self.errorHandlers = []
        
    def addErrorHandler(self, handler):
        '''Add a handler function taking two arguments: a string describing
        what operation was in process, and a string containing the
        formatted traceback. If an exception is raised inside the handler,
        it will be ignored.'''
        # TODO: inspect function to make sure it has
        # the right number of arguments.
        self.errorHandlers.append(handler)    

    def onDepthRetrievalError(self, pair, tracebackText):
        msg = "Error while retrieving %s depth" % pair
        for h in self.errorHandlers:
            try:
                h(msg, tracebackText)
            except:
                pass

    def onDepthHandlingError(self, pair, handler, tracebackText):
        msg = "Error in handler %r for %s depth" % (handler, pair)
        for h in self.errorHandlers:
            try:
                h(msg, tracebackText)
            except:
                pass

    def onTradeHistoryRetrievalError(self, pair, tracebackText):
        msg = "Error while retrieving %s trade history" % pair
        for h in self.errorHandlers:
            try:
                h(msg, tracebackText)
            except:
                pass

    def onTradeHistoryHandlingError(self, pair, handler, tracebackText):
        msg = "Error in handler %r for %s trade history" % (handler, pair)
        for h in self.errorHandlers:
            try:
                h(msg, tracebackText)
            except:
                pass
        
    def mergeTradeHistory(self, pair, history):
        keys = self.tradeHistoryIds.setdefault(pair, set())
        prevItems = self.tradeHistoryItems.get(pair, [])
        newItems = []
        
        # Remove old items
        now = datetime.datetime.now()
        dt = datetime.timedelta(minutes = self.bufferSpanMinutes)
        for h in prevItems:
            if h.date - now > dt:
                keys.remove(h.tid)
            else:
                keys.add(h.tid)
                newItems.append(h)

        # Add new items        
        for h in history:
            if h.tid not in keys:
                keys.add(h.tid)
                newItems.append(h)

        self.tradeHistoryItems[pair] = newItems
        
    def addTrader(self, trader):
        if trader.onNewDepth.__func__ is not TraderBase.onNewDepth.__func__:
            self.addDepthHandler(trader.onNewDepth, trader.pairs)
            
        if trader.onNewTradeHistory.__func__ is not TraderBase.onNewTradeHistory.__func__:
            self.addTradeHistoryHandler(trader.onNewTradeHistory, trader.pairs)

        if trader.onLoopEnd.__func__ is not TraderBase.onLoopEnd.__func__:
            self.addLoopEndHandler(trader.onLoopEnd)
            
        self.traders.add(trader)
        
    def addDepthHandler(self, handler, pairs=btceapi.all_pairs):
        for p in pairs:
            validatePair(p)
          
        self.depthHandlers.append((handler, pairs))
        
    def addTradeHistoryHandler(self, handler, pairs=btceapi.all_pairs):
        for p in pairs:
            validatePair(p)

        self.tradeHistoryHandlers.append((handler, pairs))
        
    def addLoopEndHandler(self, handler):
        self.loopEndHandlers.append(handler)

    def setCollectionInterval(self, interval_seconds):
        self.collectionInterval = interval_seconds
        
    def start(self):
        self.running = True
        self.thread = threading.Thread(target = _runBot, args=(self,))
        self.thread.start()
        
    def stop(self):
        self.running = False
        self.thread.join()
        
