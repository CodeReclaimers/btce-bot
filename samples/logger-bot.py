# Copyright (c) 2013 Alan McIntyre

import time

import btceapi
import btcebot

class MarketDataLogger(btcebot.TraderBase):
    '''
    This "trader" simply logs all of the updates it receives from the bot.
    '''
    
    def __init__(self, pairs, database_path):
        btcebot.TraderBase.__init__(self, pairs)
        self.database_path = database_path
        self.db = None
        self.trade_history_seen = {}
       
    def getDB(self):
        # The database is lazily created here instead of the constructor
        # so that it can be created and used in the bot's thread.
        if self.db is None:
            self.db = btcebot.MarketDatabase(self.database_path)

        return self.db
    
    def onExit(self):
        if self.db is not None:
            self.db.close()
       
    # This overrides the onNewDepth method in the TraderBase class, so the 
    # framework will automatically pick it up and send updates to it.
    def onNewDepth(self, t, pair, asks, bids):
        print "%s Entering new %s depth" % (t, pair)
        self.getDB().insertDepth(t, pair, asks, bids)

    # This overrides the onNewTradeHistory method in the TraderBase class, so the 
    # framework will automatically pick it up and send updates to it.
    def onNewTradeHistory(self, t, pair, trades):
        history = self.trade_history_seen.setdefault(pair, set())
        
        new_trades = filter(lambda trade: trade.tid not in history, trades)
        if new_trades:
            print "%s Entering %d new %s trades" % (t, len(new_trades), pair)
            self.getDB().insertTradeHistory(new_trades)
            history.update(t.tid for t in new_trades)
        
       
def onBotError(msg, tracebackText):
    tstr = time.strftime("%Y/%m/%d %H:%M:%S")
    print "%s - %s" % (tstr, msg)
    open("logger-bot-error.log", "a").write(
        "%s - %s\n%s\n%s\n" % (tstr, msg, tracebackText, "-"*80))
            
def run(database_path):
    logger= MarketDataLogger(btceapi.all_pairs, database_path)
    #logger= MarketDataLogger(("btc_usd", "ltc_usd"), database_path)

    # Create a bot and add the logger to it.
    bot = btcebot.Bot()
    bot.addTrader(logger)

    # Add an error handler so we can print info about any failures
    bot.addErrorHandler(onBotError)    

    # The bot will provide the logger with updated information every
    # 60 seconds.
    bot.setCollectionInterval(60)
    bot.start()
    print "Running; press Ctrl-C to stop"

    try:
        while 1:
            # you can do anything else you prefer in this loop while 
            # the bot is running in the background
            time.sleep(3600)
            
    except KeyboardInterrupt:
        print "Stopping..."
    finally:    
        bot.stop()
            
        
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Simple range trader example.')
    parser.add_argument('--db-path', default='btce.db',
                        help='Path to the logger database.')

    args = parser.parse_args()
    run(args.db_path)
