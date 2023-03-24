from datamodel import OrderDepth, TradingState, Order

class Trader:
    def __init__(self):
        self.cash = {product : 0 for product in ["PEARLS", "BANANAS", "COCONUTS", "PINA_COLADAS" ]}
        self.mid_ewmas = {
            "PEARLS" : 10000,
            "BANANAS" : None,
            "COCONUTS" : None,
            "PINA_COLADAS" : None,
        }
        self.fairs = {
            "PEARLS" : 10000,
            "BANANAS" : None,
            "COCONUTS" : None,
            "PINA_COLADAS" : None,
        }
        self.own_traded_quantity = {
            "PEARLS": 0,
            "BANANAS": 0,
            "COCONUTS": 0,
            "PINA_COLADAS": 0
        }
        self.market_traded_quantity = {
            "PEARLS": 0,
            "BANANAS": 0,
            "COCONUTS": 0,
            "PINA_COLADAS": 0
        }
        
    edges = {
        "PEARLS" : 0.5,
        "BANANAS" : 1,
        "COCONUTS": 1,
        "PINA_COLADAS": 1
    }
    
    position_limits = {
        "PEARLS" : 20,
        "BANANAS" : 20,
        "COCONUTS": 600,
        "PINA_COLADAS": 300
    }
    
    decay_factors = {
        "PEARLS" : 0.99,
        "BANANAS" : 0.9,
        "COCONUTS" : 0.9,
        "PINA_COLADAS" : 0.9
    }

    def run(self, state: TradingState):
        def get_best_bid(state, product):
            order_depth = state.order_depths[product]
            if len(order_depth.buy_orders) == 0:
                return None, None
            else:
                best_bid = max(order_depth.buy_orders.keys())
                return best_bid, order_depth.buy_orders[best_bid]
    
        def get_best_ask(state, product):
            order_depth = state.order_depths[product]
            if len(order_depth.sell_orders) == 0:
                return None, None
            else:
                best_ask = min(order_depth.sell_orders.keys())
                return best_ask, order_depth.sell_orders[best_ask]
            
        def get_mid(state, product):
            bbid, _ = get_best_bid(state, product)
            bask, _ = get_best_ask(state, product)
            if (bbid != None) and (bask != None):
                return (bbid + bask) / 2
            else:
                return None
            
        result = {}

        for product in state.order_depths:
            # First update mid_ewmas
            mid = get_mid(state, product)
            decay_factor = self.decay_factors[product]
            if mid is not None:
                if self.mid_ewmas[product] is None:
                    self.mid_ewmas[product] = mid
                else:
                    self.mid_ewmas[product] = \
                        decay_factor * self.mid_ewmas[product] \
                        + (1 - decay_factor) * mid
        
        for product in state.order_depths:
            # Update fairs:
            if product == "BANANAS" or product == "PEARLS":
                self.fairs[product] = self.mid_ewmas[product]
            elif product == "COCONUTS":
                pina_colada_mid = get_mid(state,"PINA_COLADAS")
                if pina_colada_mid is not None and self.mid_ewmas[product] is not None:
                    self.fairs[product] = self.mid_ewmas[product] * (1 + 0.5 * (pina_colada_mid / self.mid_ewmas["PINA_COLADAS"] - 1))
            elif product == "PINA_COLADAS":
                coconut_mid = get_mid(state, "COCONUTS")
                if coconut_mid is not None and self.mid_ewmas[product] is not None:
                    self.fairs[product] = self.mid_ewmas[product] * (1 + 0.8 * (coconut_mid / self.mid_ewmas["COCONUTS"] - 1))

            # Process trades to get cash amount:
            if product in state.own_trades.keys():
                for trade in state.own_trades[product]:
                    if trade.timestamp == state.timestamp - 100:
                        self.own_traded_quantity[product] += trade.quantity
                        if trade.buyer == "SUBMISSION":
                            self.cash[product] -= trade.price * trade.quantity
                        if trade.seller == "SUBMISSION":
                            self.cash[product] += trade.price * trade.quantity
            if product in state.market_trades.keys():
                for trade in state.market_trades[product]:
                    if trade.timestamp == state.timestamp - 100:
                        self.market_traded_quantity[product] += trade.quantity

        for product in state.order_depths:
            # Send orders:
            orders = []
            fair_value = self.fairs[product]
            edge = self.edges[product]
            best_bid, best_bid_quantity = get_best_bid(state, product)
            best_ask, best_ask_quantity = get_best_ask(state, product)
            current_pos = state.position[product] if product in state.position.keys() else 0
            max_ask_size = current_pos + self.position_limits[product]
            max_bid_size = self.position_limits[product] - current_pos

            # Print fair info:
            print("Fair info:", product, best_bid, fair_value, best_ask, current_pos, max_bid_size, max_ask_size)

            if product in ["BANANAS", "PEARLS"]:
                if (best_bid is not None) and (fair_value is not None) and (best_bid > fair_value):
                    order_size = min(best_bid_quantity, max_ask_size)
                    orders.append(Order(product, best_bid, -order_size))
                    max_ask_size = max_ask_size - order_size
                            
                if (best_ask is not None) and (fair_value is not None) and (best_ask < fair_value):
                    order_size = min(-best_ask_quantity, max_bid_size)
                    orders.append(Order(product, best_ask, order_size))
                    max_bid_size = max_bid_size - order_size
            
            if best_bid is not None and fair_value is not None:
                if best_bid + 1 < fair_value - edge:
                    if max_bid_size > 0:
                        agg_size = max(int(max_bid_size * 0.9), 1)
                        pas_size = max_bid_size - agg_size
                        orders.append(Order(product, best_bid + 1, agg_size))
                        orders.append(Order(product, best_bid, pas_size))
                elif best_bid < fair_value - edge:
                    orders.append(Order(product, best_bid, max_bid_size))
            else:
                orders.append(Order(product, 1, max_bid_size))
            
            if best_ask is not None and fair_value is not None:
                if best_ask - 1 > fair_value + edge:
                    if max_ask_size > 0:
                        agg_size = max(int(max_ask_size * 0.9), 1)
                        pas_size = max_ask_size - agg_size
                        orders.append(Order(product, best_ask - 1, -agg_size))
                        orders.append(Order(product, best_ask, -pas_size))
                elif best_ask > fair_value + edge:
                    orders.append(Order(product, best_ask, -max_ask_size))
            else:
                orders.append(Order(product, 99999, -max_ask_size))

            # Remove orders with 0 quantity
            orders = [order for order in orders if order.quantity != 0]
            for order in orders:
                print("Order:", product, order)
            result[product] = orders

        # Some pnl debug
        for product in state.order_depths:
            if (product in self.mid_ewmas.keys()) and (product in state.position.keys()):
                print(
                    "PNL info:",
                    product, 
                    state.position[product] * self.mid_ewmas[product] + self.cash[product],
                    self.market_traded_quantity[product],
                    self.own_traded_quantity[product]
                )

        return result





            


