"""Workflow orchestration engine for DAG execution."""

import logging
from typing import List, Dict, Set, Optional
from collections import defaultdict

from backend.db import db
from backend.models.job import Job
from backend.models.workflow import JobDependency

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Execute job workflows with dependency resolution."""

    @staticmethod
    def build_dag(job_ids: List[int]) -> Dict[int, List[int]]:
        """Build dependency graph from job IDs."""
        session = db.get_session()
        dependencies = session.query(JobDependency).filter(
            JobDependency.parent_job_id.in_(job_ids)
        ).all()

        graph = defaultdict(list)
        for dep in dependencies:
            graph[dep.parent_job_id].append(dep.child_job_id)

        return dict(graph)

    @staticmethod
    def topological_sort(job_ids: List[int]) -> Optional[List[int]]:
        """Sort jobs by dependency order (topological sort)."""
        graph = WorkflowEngine.build_dag(job_ids)

        # Calculate in-degrees
        in_degree = {job_id: 0 for job_id in job_ids}
        for parent, children in graph.items():
            for child in children:
                if child in in_degree:
                    in_degree[child] += 1

        # Kahn's algorithm
        queue = [job_id for job_id in job_ids if in_degree[job_id] == 0]
        sorted_jobs = []

        while queue:
            current = queue.pop(0)
            sorted_jobs.append(current)

            if current in graph:
                for child in graph[current]:
                    if child in in_degree:
                        in_degree[child] -= 1
                        if in_degree[child] == 0:
                            queue.append(child)

        # Detect cycles
        if len(sorted_jobs) != len(job_ids):
            logger.error("Cycle detected in job dependency graph")
            return None

        return sorted_jobs

    @staticmethod
    def get_executable_jobs(workflow_id: int, completed: Set[int]) -> List[int]:
        """Get jobs ready to execute (dependencies satisfied)."""
        session = db.get_session()

        # Get all jobs in workflow
        all_jobs = session.query(Job).filter_by(workflow_id=workflow_id).all()
        job_ids = [j.id for j in all_jobs]

        graph = WorkflowEngine.build_dag(job_ids)
        executable = []

        for job_id in job_ids:
            if job_id in completed:
                continue

            # Check if all parents completed
            parents = [p for p, children in graph.items() if job_id in children]
            if all(p in completed for p in parents):
                executable.append(job_id)

        return executable

    @staticmethod
    def validate_dag(job_ids: List[int]) -> Dict[str, any]:
        """Validate DAG structure (no cycles, valid dependencies)."""
        sorted_jobs = WorkflowEngine.topological_sort(job_ids)

        if sorted_jobs is None:
            return {
                "valid": False,
                "error": "Cycle detected in dependency graph",
            }

        graph = WorkflowEngine.build_dag(job_ids)
        edge_count = sum(len(children) for children in graph.values())

        return {
            "valid": True,
            "job_count": len(job_ids),
            "edge_count": edge_count,
            "execution_order": sorted_jobs,
        }

    @staticmethod
    def add_dependency(parent_id: int, child_id: int, condition: str = "on_success") -> bool:
        """Add job dependency edge."""
        if parent_id == child_id:
            logger.error("Cannot create self-dependency")
            return False

        session = db.get_session()

        # Check for cycle before adding
        existing_deps = session.query(JobDependency).all()
        temp_graph = defaultdict(list)
        for dep in existing_deps:
            temp_graph[dep.parent_job_id].append(dep.child_job_id)
        temp_graph[parent_id].append(child_id)

        # Would this create a cycle?
        visited = set()
        def has_cycle(node):
            if node in visited:
                return True
            visited.add(node)
            for child in temp_graph.get(node, []):
                if has_cycle(child):
                    return True
            visited.remove(node)
            return False

        if has_cycle(parent_id):
            logger.error(f"Adding dependency {parent_id}->{child_id} would create cycle")
            return False

        # Add dependency
        dep = JobDependency(
            parent_job_id=parent_id,
            child_job_id=child_id,
            condition=condition,
        )
        session.add(dep)
        session.commit()
        logger.info(f"Added dependency: {parent_id} -> {child_id} (condition: {condition})")
        return True

    @staticmethod
    def remove_dependency(parent_id: int, child_id: int) -> bool:
        """Remove job dependency edge."""
        session = db.get_session()
        dep = session.query(JobDependency).filter_by(
            parent_job_id=parent_id,
            child_job_id=child_id,
        ).first()

        if dep:
            session.delete(dep)
            session.commit()
            logger.info(f"Removed dependency: {parent_id} -> {child_id}")
            return True
        return False


workflow_engine = WorkflowEngine()
