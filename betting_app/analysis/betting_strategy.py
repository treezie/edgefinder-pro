from typing import Dict, Any, List
import math


class BettingStrategy:
    """
    Provides betting strategy recommendations based on bankroll management
    and value betting principles
    """

    def __init__(self, bankroll: float = 1000.0):
        self.bankroll = bankroll
        self.min_edge = 0.03  # Minimum 3% edge required
        self.max_stake_percentage = 0.05  # Max 5% of bankroll per bet
        self.kelly_fraction = 0.25  # Quarter Kelly for safety

    def calculate_kelly_stake(self, probability: float, odds: float, bankroll: float) -> float:
        """
        Calculate optimal stake using Kelly Criterion
        Formula: f = (bp - q) / b
        where:
        - f = fraction of bankroll to wager
        - b = odds received (decimal odds - 1)
        - p = probability of winning
        - q = probability of losing (1 - p)
        """
        if odds <= 1.0 or probability <= 0 or probability >= 1:
            return 0.0

        b = odds - 1  # Convert decimal odds to net odds
        p = probability
        q = 1 - p

        kelly = (b * p - q) / b

        # Apply fractional Kelly for safety
        kelly = kelly * self.kelly_fraction

        # Ensure stake is within limits
        kelly = max(0, min(kelly, self.max_stake_percentage))

        stake = bankroll * kelly
        return round(stake, 2)

    def get_stake_recommendation(
        self,
        probability: float,
        odds: float,
        value_score: float,
        confidence: str,
        bankroll: float = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive stake recommendation with risk assessment
        """
        if bankroll is None:
            bankroll = self.bankroll

        # Calculate Kelly stake
        kelly_stake = self.calculate_kelly_stake(probability, odds, bankroll)

        # Determine stake level based on confidence and value
        if value_score < self.min_edge:
            stake_category = "Pass"
            recommended_stake = 0.0
            risk_level = "N/A"
            reasoning = "No positive edge detected - avoid this bet"

        elif confidence == "High" and value_score > 0.10:
            stake_category = "Strong"
            recommended_stake = kelly_stake
            risk_level = "Moderate"
            reasoning = "High confidence with strong value - optimal Kelly stake"

        elif confidence in ["High", "Medium"] and value_score > 0.05:
            stake_category = "Standard"
            recommended_stake = kelly_stake * 0.75  # Reduce Kelly by 25%
            risk_level = "Low-Moderate"
            reasoning = "Good value with reasonable confidence - conservative stake"

        elif value_score > 0.03:
            stake_category = "Small"
            recommended_stake = kelly_stake * 0.5  # Reduce Kelly by 50%
            risk_level = "Low"
            reasoning = "Marginal edge - minimal stake for portfolio diversification"

        else:
            stake_category = "Pass"
            recommended_stake = 0.0
            risk_level = "N/A"
            reasoning = "Insufficient edge for recommended bet"

        # Calculate potential return
        potential_profit = recommended_stake * (odds - 1) if recommended_stake > 0 else 0
        potential_return = recommended_stake + potential_profit if recommended_stake > 0 else 0

        # ROI if bet wins
        roi_percentage = ((potential_return / recommended_stake) - 1) * 100 if recommended_stake > 0 else 0

        return {
            "stake_category": stake_category,
            "recommended_stake": round(recommended_stake, 2),
            "risk_level": risk_level,
            "reasoning": reasoning,
            "kelly_fraction": self.kelly_fraction,
            "potential_profit": round(potential_profit, 2),
            "potential_return": round(potential_return, 2),
            "roi_percentage": round(roi_percentage, 1),
            "as_percentage_of_bankroll": round((recommended_stake / bankroll) * 100, 2) if bankroll > 0 else 0
        }

    def get_portfolio_recommendation(self, bets: List[Dict[str, Any]], bankroll: float = None) -> Dict[str, Any]:
        """
        Analyze a portfolio of bets and provide overall recommendations
        """
        if bankroll is None:
            bankroll = self.bankroll

        total_stake = 0
        recommended_bets = []
        expected_value = 0

        for bet in bets:
            probability = bet.get("probability", 0)
            odds = bet.get("odds", 0)
            value_score = bet.get("value_score", 0)
            confidence = bet.get("confidence", "Low")

            stake_rec = self.get_stake_recommendation(probability, odds, value_score, confidence, bankroll)

            if stake_rec["recommended_stake"] > 0:
                total_stake += stake_rec["recommended_stake"]
                expected_value += (probability * stake_rec["potential_profit"]) - ((1 - probability) * stake_rec["recommended_stake"])
                recommended_bets.append({
                    "bet": bet.get("selection", "Unknown"),
                    "stake": stake_rec["recommended_stake"],
                    "odds": odds
                })

        exposure_percentage = (total_stake / bankroll) * 100 if bankroll > 0 else 0

        return {
            "total_recommended_stake": round(total_stake, 2),
            "exposure_percentage": round(exposure_percentage, 2),
            "number_of_bets": len(recommended_bets),
            "expected_value": round(expected_value, 2),
            "recommended_bets": recommended_bets,
            "portfolio_health": "Healthy" if exposure_percentage < 20 else "Moderate" if exposure_percentage < 35 else "High Risk"
        }

    def optimize_portfolio_stakes(self, recommendations: List[Dict[str, Any]], max_exposure_percent: float = 0.25) -> List[Dict[str, Any]]:
        """
        Scales down stakes if total exposure exceeds the maximum allowed percentage of bankroll.
        """
        if not recommendations:
            return []

        total_stake = sum(r["recommended_stake"] for r in recommendations)
        
        # Avoid division by zero
        if total_stake == 0:
            return recommendations

        # Calculate current exposure
        # Assuming all recommendations use the same bankroll, we can derive it from one entry
        # or pass it in. Here we'll infer it from the first entry if possible, 
        # otherwise use self.bankroll.
        
        # Try to find bankroll from the first recommendation's percentage
        # stake / (percent / 100) = bankroll
        # But safer to just rely on the passed in bankroll if available, or self.bankroll
        # Since we don't have bankroll passed in here easily without changing signature significantly,
        # we will use self.bankroll. Ideally, the strategy instance has the correct bankroll.
        
        max_exposure_amount = self.bankroll * max_exposure_percent

        if total_stake > max_exposure_amount:
            scaling_factor = max_exposure_amount / total_stake
            
            for rec in recommendations:
                original_stake = rec["recommended_stake"]
                new_stake = round(original_stake * scaling_factor, 2)
                
                rec["recommended_stake"] = new_stake
                
                # Recalculate dependent values
                odds = rec["odds"]
                potential_profit = new_stake * (odds - 1) if new_stake > 0 else 0
                potential_return = new_stake + potential_profit if new_stake > 0 else 0
                
                rec["potential_profit"] = round(potential_profit, 2)
                rec["potential_return"] = round(potential_return, 2)
                
                # ROI percentage stays the same
                
                # Update percentage of bankroll
                rec["as_percentage_of_bankroll"] = round((new_stake / self.bankroll) * 100, 2) if self.bankroll > 0 else 0
                rec["kelly_percentage"] = rec["as_percentage_of_bankroll"]

        return recommendations
