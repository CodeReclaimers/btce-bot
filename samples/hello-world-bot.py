#!/usr/bin/python
# Copyright (c) 2013 Alan McIntyre

import decimal
import time

import btceapi
import btcebot

class RangeTrader(btcebot.TraderBase):
    '''
    This is a simple trader that handles a single currency pair, selling
    all available inventory if price is above sell_price, buying with
    all available funds if price is below buy_price.  Use for actual trading
    at your own risk (and remember this is just a sample, not a recommendation
    on how to make money trading using this framework).
    '''
    def __init__(self, api, pair, buy_price, sell_price, live_trades = False):
        btcebot.TraderBase.__init__(self, (pair,))
        self.api = api
        self.pair = pair
        self.buy_price = buy_price
        self.sell_price = sell_price
        self.live_trades = live_trades
        
        self.current_lowest_ask = None
        self.current_highest_bid = None
        
        # Apparently the API adds the fees to the amount you submit,
        # so dial back the order just enough to make up for the 
        # 0.2% trade fee.
        self.fee_adjustment = decimal.Decimal("0.998")
        
    def _attemptBuy(self, price, amount):
        info = self.api.getInfo()
        curr1, curr2 = self.pair.split("_")
        
        # Limit order to what we can afford to buy.
        available = getattr(info, "balance_" + curr2)
        max_buy = available / price
        buy_amount = min(max_buy, amount) * self.fee_adjustment
        if buy_amount >= btceapi.min_orders[self.pair]:
            print "attempting to buy %s %s at %s for %s %s" % (buy_amount, 
                curr1.upper(), price, buy_amount*price, curr2.upper())
            if self.live_trades:
                r = self.api.trade(self.pair, "buy", price, buy_amount)
                print "\tReceived %s %s" % (r.received, curr1.upper())
                # If the order didn't fill completely, cancel the remaining order
                if r.order_id != 0:
                    print "\tCanceling unfilled portion of order"
                    self.api.cancelOrder(r.order_id)

    def _attemptSell(self, price, amount):
        info = self.api.getInfo()
        curr1, curr2 = self.pair.split("_")
        
        # Limit order to what we have available to sell.
        available = getattr(info, "balance_" + curr1)
        sell_amount = min(available, amount) * self.fee_adjustment
        if sell_amount >= btceapi.min_orders[self.pair]:
            print "attempting to sell %s %s at %s for %s %s" % (sell_amount,
                curr1.upper(), price, sell_amount*price, curr2.upper())
            if self.live_trades:
                r = self.api.trade(self.pair, "sell", price, sell_amount)
                print "\tReceived %s %s" % (r.received, curr2.upper())
                # If the order didn't fill completely, cancel the remaining order
                if r.order_id != 0:
                    print "\tCanceling unfilled portion of order"
                    self.api.cancelOrder(r.order_id)
            
    # This overrides the onNewDepth method in the TraderBase class, so the 
    # framework will automatically pick it up and send updates to it.
    def onNewDepth(self, t, pair, asks, bids):
        ask_price, ask_amount = asks[0]
        bid_price, bid_amount = bids[0]
        if ask_price <= self.buy_price:
            self._attemptBuy(ask_price, ask_amount)
        elif bid_price >= self.sell_price:
            self._attemptSell(bid_price, bid_amount)

            
def onBotError(msg, tracebackText):
    tstr = time.strftime("%Y/%m/%d %H:%M:%S")
    print "%s - %s" % (tstr, msg)
    open("hello-world-bot-error.log", "a").write(
        "%s - %s\n%s\n%s\n" % (tstr, msg, tracebackText, "-"*80))
            
def run(key_file, buy_floor, sell_ceiling, live_trades):        
    # Load the keys and create an API object from the first one.
    handler = btceapi.KeyHandler(key_file, resaveOnDeletion=True)
    key = handler.getKeys()[0]
    print "Trading with key %s" % key
    api = btceapi.TradeAPI(key, handler=handler)
            
    # Create a trader that handles LTC/USD trades in the given range.
    trader = RangeTrader(api, "ltc_usd", buy_floor, sell_ceiling, live_trades)

    # Create a bot and add the trader to it.
    bot = btcebot.Bot()
    bot.addTrader(trader)
    
    # Add an error handler so we can print info about any failures
    bot.addErrorHandler(onBotError)    

    # The bot will provide the traders with updated information every
    # 15 seconds.
    bot.setCollectionInterval(15)
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
    parser.add_argument('key_file', 
                        help='Path to a file containing key/secret/nonce data.')
    parser.add_argument('buy_floor', type=decimal.Decimal,
                        help='Price at or below which we will buy.')
    parser.add_argument('sell_ceiling', type=decimal.Decimal,
                        help='Price at or above which we will sell.')
    parser.add_argument('--live-trades', default=False, action="store_true",
                        help='Actually make trades.')
    
    args = parser.parse_args()
    
    if args.buy_floor >= args.sell_ceiling:
        raise Exception("Buy price should probably be below sell price!")
    
    run(args.key_file, args.buy_floor, args.sell_ceiling, args.live_trades) 
