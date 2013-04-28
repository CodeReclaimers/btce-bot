

class TraderBase(object):
    def __init__(self, api):
        self.api = api
    
    def addToBot(self, bot):
        if self.onNewDepth.__func__ is not TraderBase.onNewDepth.__func__:
            bot.addDepthHandler(self.onNewDepth, (self.pair,))
            
        if self.onNewTradeHistory.__func__ is not TraderBase.onNewTradeHistory.__func__:
            bot.addTradeHistoryHandler(self.onNewTradeHistory, (self.pair,))

        if self.onLoopEnd.__func__ is not TraderBase.onLoopEnd.__func__:
            bot.addLoopEndHandler(self.onLoopEnd)
        
    def onNewDepth(self, t, pair, asks, bids):
        pass

    def onNewTradeHistory(self, t, pair, trades):
        pass
        
    def onLoopEnd(self, t):
        pass
