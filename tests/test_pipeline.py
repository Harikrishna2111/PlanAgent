"""
Tests for the Agentic AI Architectural Design Framework.

Run: python -m pytest tests/test_pipeline.py -v
  or: python tests/test_pipeline.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    DesignRequirements, RoomRequirement, RoomType,
    SpatialRelationship, RelationshipType, Room, FloorPlan,
)
from agents.requirement_agent import RuleBasedRequirementAgent
from spatial.graph import build_spatial_graph, graph_summary
from generation.floor_plan_generator import generate_floor_plans
from evaluation.spatial_critic import SpatialCritic
from agents.optimization_agent import optimize_floor_plan


EXAMPLE_INPUT = (
    "Design a 2BHK house on a 40 x 60 ft plot with two bedrooms, "
    "two bathrooms, kitchen, living room and dining area. "
    "The kitchen should be near the dining area, "
    "bedrooms should be close to bathrooms, "
    "and the entrance should connect to the living room."
)


class TestRequirementAgent(unittest.TestCase):

    def setUp(self):
        self.agent = RuleBasedRequirementAgent()

    def test_plot_extraction(self):
        req = self.agent.parse(EXAMPLE_INPUT)
        self.assertEqual(req.plot_width, 40.0)
        self.assertEqual(req.plot_height, 60.0)

    def test_room_extraction(self):
        req = self.agent.parse(EXAMPLE_INPUT)
        room_types = [r.room_type for r in req.rooms]
        self.assertIn(RoomType.BEDROOM, room_types)
        self.assertIn(RoomType.BATHROOM, room_types)
        self.assertIn(RoomType.KITCHEN, room_types)
        self.assertIn(RoomType.LIVING_ROOM, room_types)
        self.assertIn(RoomType.DINING, room_types)
        # Should have 2 bedrooms, 2 bathrooms
        bedrooms = [r for r in req.rooms if r.room_type == RoomType.BEDROOM]
        bathrooms = [r for r in req.rooms if r.room_type == RoomType.BATHROOM]
        self.assertEqual(len(bedrooms), 2)
        self.assertEqual(len(bathrooms), 2)

    def test_relationship_extraction(self):
        req = self.agent.parse(EXAMPLE_INPUT)
        # Bedroom-Bathroom near relationships
        near_rels = [r for r in req.relationships if r.relationship == RelationshipType.NEAR]
        self.assertGreaterEqual(len(near_rels), 2)
        # Connected_to relationship
        conn_rels = [r for r in req.relationships if r.relationship == RelationshipType.CONNECTED_TO]
        self.assertGreaterEqual(len(conn_rels), 1)

    def test_entrance_auto_added(self):
        req = self.agent.parse("Design a house on a 30x40 plot with one bedroom")
        entrance = [r for r in req.rooms if r.room_type == RoomType.ENTRANCE]
        self.assertEqual(len(entrance), 1)

    def test_json_serialization(self):
        req = self.agent.parse(EXAMPLE_INPUT)
        json_str = req.to_json()
        req2 = DesignRequirements.from_json(json_str)
        self.assertEqual(req.plot_width, req2.plot_width)
        self.assertEqual(len(req.rooms), len(req2.rooms))


class TestSpatialGraph(unittest.TestCase):

    def test_graph_construction(self):
        agent = RuleBasedRequirementAgent()
        req = agent.parse(EXAMPLE_INPUT)
        G = build_spatial_graph(req)
        self.assertEqual(G.number_of_nodes(), len(req.rooms))
        self.assertEqual(G.number_of_edges(), len(req.relationships))

    def test_graph_summary(self):
        agent = RuleBasedRequirementAgent()
        req = agent.parse(EXAMPLE_INPUT)
        G = build_spatial_graph(req)
        summary = graph_summary(G)
        self.assertIn("rooms", summary)
        self.assertIn("relationships", summary)


class TestFloorPlanGenerator(unittest.TestCase):

    def setUp(self):
        agent = RuleBasedRequirementAgent()
        self.req = agent.parse(EXAMPLE_INPUT)

    def test_generates_candidates(self):
        plans = generate_floor_plans(self.req, num_candidates=3)
        self.assertGreaterEqual(len(plans), 1)

    def test_rooms_inside_plot(self):
        plans = generate_floor_plans(self.req, num_candidates=1)
        for plan in plans:
            for room in plan.rooms:
                self.assertGreaterEqual(room.x, 0)
                self.assertGreaterEqual(room.y, 0)
                self.assertLessEqual(room.right, plan.plot_width + 0.1)
                self.assertLessEqual(room.top, plan.plot_height + 0.1)

    def test_no_overlaps(self):
        plans = generate_floor_plans(self.req, num_candidates=1)
        for plan in plans:
            for i, r1 in enumerate(plan.rooms):
                for r2 in plan.rooms[i+1:]:
                    self.assertFalse(r1.overlaps(r2),
                                     f"{r1.name} overlaps {r2.name}")


class TestSpatialCritic(unittest.TestCase):

    def setUp(self):
        agent = RuleBasedRequirementAgent()
        self.req = agent.parse(EXAMPLE_INPUT)
        self.critic = SpatialCritic()

    def test_scoring(self):
        plans = generate_floor_plans(self.req, num_candidates=1)
        result = self.critic.evaluate(plans[0], self.req)
        self.assertGreater(result.total_score, 0.0)
        self.assertLessEqual(result.total_score, 1.0)

    def test_all_dimensions_present(self):
        plans = generate_floor_plans(self.req, num_candidates=1)
        result = self.critic.evaluate(plans[0], self.req)
        expected_dims = [
            "room_completeness", "room_dimensions", "overlap_penalty",
            "boundary_compliance", "adjacency", "connectivity",
            "separation", "space_utilization",
        ]
        for dim in expected_dims:
            self.assertIn(dim, result.dimension_scores)


class TestOptimizer(unittest.TestCase):

    def setUp(self):
        agent = RuleBasedRequirementAgent()
        self.req = agent.parse(EXAMPLE_INPUT)

    def test_optimization_runs(self):
        plans = generate_floor_plans(self.req, num_candidates=1)
        optimized, result, history = optimize_floor_plan(
            plans[0], self.req, max_iterations=50
        )
        self.assertIsNotNone(optimized)
        self.assertGreater(result.total_score, 0.0)
        self.assertGreater(len(history), 0)

    def test_optimization_improves_or_maintains(self):
        """Optimization should not make things worse."""
        plans = generate_floor_plans(self.req, num_candidates=1)
        critic = SpatialCritic()
        before = critic.evaluate(plans[0], self.req)
        optimized, after, _ = optimize_floor_plan(
            plans[0], self.req, max_iterations=100
        )
        self.assertGreaterEqual(after.total_score, before.total_score - 0.01)


class TestRoomGeometry(unittest.TestCase):

    def test_overlap_detection(self):
        r1 = Room("A", RoomType.BEDROOM, 0, 0, 10, 10)
        r2 = Room("B", RoomType.BEDROOM, 5, 5, 10, 10)
        self.assertTrue(r1.overlaps(r2))

    def test_no_overlap(self):
        r1 = Room("A", RoomType.BEDROOM, 0, 0, 10, 10)
        r2 = Room("B", RoomType.BEDROOM, 10, 0, 10, 10)
        self.assertFalse(r1.overlaps(r2))

    def test_shares_edge(self):
        r1 = Room("A", RoomType.BEDROOM, 0, 0, 10, 10)
        r2 = Room("B", RoomType.BEDROOM, 10, 0, 10, 10)
        self.assertTrue(r1.shares_edge(r2))

    def test_distance(self):
        r1 = Room("A", RoomType.BEDROOM, 0, 0, 10, 10)
        r2 = Room("B", RoomType.BEDROOM, 20, 0, 10, 10)
        dist = r1.distance_to(r2)
        self.assertAlmostEqual(dist, 20.0, places=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
