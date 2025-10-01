# src/performance/scaling_manager.py
import asyncio
import logging
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from multiprocessing import cpu_count
import aiohttp
from sqlalchemy import create_engine, pool
from sqlalchemy.orm import sessionmaker

from ..db import SessionLocal, engine
from ..models import Job, Company, UserProfile
from ..config import config

logger = logging.getLogger(__name__)

class ScalingManager:
    """Manages application scaling and performance optimization"""
    
    def __init__(self):
        self.scaling_config = config.performance_config.get("scaling", {})
        self.max_workers = self.scaling_config.get("max_workers", cpu_count())
        self.connection_pool_size = self.scaling_config.get("db_pool_size", 20)
        self.max_overflow = self.scaling_config.get("db_max_overflow", 30)
        
        # Performance monitoring
        self.performance_metrics = {
            'cpu_usage': [],
            'memory_usage': [],
            'db_connections': [],
            'response_times': [],
            'last_updated': datetime.utcnow()
        }
        
        # Initialize optimized database engine
        self._setup_optimized_db_engine()
        
        # Thread and process pools
        self.thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)
        self.process_pool = ProcessPoolExecutor(max_workers=min(4, cpu_count()))
        
    def _setup_optimized_db_engine(self):
        """Setup optimized database engine with connection pooling"""
        try:
            # Create optimized engine with connection pooling
            self.optimized_engine = create_engine(
                str(engine.url),
                poolclass=pool.QueuePool,
                pool_size=self.connection_pool_size,
                max_overflow=self.max_overflow,
                pool_pre_ping=True,
                pool_recycle=3600,  # Recycle connections every hour
                echo=False
            )
            
            # Create optimized session factory
            self.OptimizedSession = sessionmaker(bind=self.optimized_engine)
            
            logger.info(f"Optimized DB engine setup with pool_size={self.connection_pool_size}")
            
        except Exception as e:
            logger.error(f"Error setting up optimized DB engine: {e}")
            self.optimized_engine = engine
            self.OptimizedSession = SessionLocal
    
    async def get_system_metrics(self) -> Dict:
        """Get current system performance metrics"""
        try:
            # CPU and Memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Database connections
            db_pool_status = self._get_db_pool_status()
            
            # Network stats
            network = psutil.net_io_counters()
            
            metrics = {
                'timestamp': datetime.utcnow().isoformat(),
                'cpu': {
                    'usage_percent': cpu_percent,
                    'count': psutil.cpu_count(),
                    'load_avg': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
                },
                'memory': {
                    'total_gb': round(memory.total / (1024**3), 2),
                    'available_gb': round(memory.available / (1024**3), 2),
                    'used_percent': memory.percent,
                    'free_gb': round(memory.free / (1024**3), 2)
                },
                'disk': {
                    'total_gb': round(disk.total / (1024**3), 2),
                    'used_gb': round(disk.used / (1024**3), 2),
                    'free_gb': round(disk.free / (1024**3), 2),
                    'used_percent': round((disk.used / disk.total) * 100, 2)
                },
                'database': db_pool_status,
                'network': {
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                }
            }
            
            # Update performance history
            self._update_performance_history(metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {}
    
    def _get_db_pool_status(self) -> Dict:
        """Get database connection pool status"""
        try:
            pool = self.optimized_engine.pool
            return {
                'pool_size': pool.size(),
                'checked_in': pool.checkedin(),
                'checked_out': pool.checkedout(),
                'overflow': pool.overflow(),
                'invalid': pool.invalid()
            }
        except Exception as e:
            logger.error(f"Error getting DB pool status: {e}")
            return {}
    
    def _update_performance_history(self, metrics: Dict):
        """Update performance metrics history"""
        try:
            # Keep last 100 data points
            max_history = 100
            
            self.performance_metrics['cpu_usage'].append({
                'timestamp': metrics['timestamp'],
                'value': metrics['cpu']['usage_percent']
            })
            
            self.performance_metrics['memory_usage'].append({
                'timestamp': metrics['timestamp'],
                'value': metrics['memory']['used_percent']
            })
            
            # Trim history
            for key in ['cpu_usage', 'memory_usage']:
                if len(self.performance_metrics[key]) > max_history:
                    self.performance_metrics[key] = self.performance_metrics[key][-max_history:]
            
            self.performance_metrics['last_updated'] = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error updating performance history: {e}")
    
    async def optimize_database_queries(self) -> Dict:
        """Optimize database performance"""
        optimizations_applied = []
        
        try:
            db = self.OptimizedSession()
            
            # Analyze slow queries and suggest optimizations
            slow_queries = self._analyze_slow_queries(db)
            
            # Optimize indexes
            index_optimizations = self._optimize_indexes(db)
            optimizations_applied.extend(index_optimizations)
            
            # Clean up old data
            cleanup_results = self._cleanup_old_data(db)
            optimizations_applied.extend(cleanup_results)
            
            # Update table statistics
            self._update_table_statistics(db)
            optimizations_applied.append("Updated table statistics")
            
            db.close()
            
            return {
                'status': 'success',
                'optimizations_applied': optimizations_applied,
                'slow_queries_found': len(slow_queries)
            }
            
        except Exception as e:
            logger.error(f"Error optimizing database: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _analyze_slow_queries(self, db) -> List[Dict]:
        """Analyze and identify slow queries"""
        # This would typically analyze query logs
        # For SQLite, we'll simulate this
        return []
    
    def _optimize_indexes(self, db) -> List[str]:
        """Create or optimize database indexes"""
        optimizations = []
        
        try:
            # Create indexes for common query patterns
            indexes_to_create = [
                "CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(is_active)",
                "CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_jobs_company_id ON jobs(company_id)",
                "CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name)",
                "CREATE INDEX IF NOT EXISTS idx_matches_user_id ON matches(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_matches_score ON matches(overall_score)",
            ]
            
            for index_sql in indexes_to_create:
                try:
                    db.execute(index_sql)
                    optimizations.append(f"Created index: {index_sql.split()[-1]}")
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Error creating index: {e}")
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error optimizing indexes: {e}")
        
        return optimizations
    
    def _cleanup_old_data(self, db) -> List[str]:
        """Clean up old and unnecessary data"""
        cleanup_results = []
        
        try:
            # Remove old inactive jobs (older than 90 days)
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            
            old_jobs = db.query(Job).filter(
                Job.is_active == False,
                Job.created_at < cutoff_date
            ).delete()
            
            if old_jobs > 0:
                cleanup_results.append(f"Removed {old_jobs} old inactive jobs")
            
            # Clean up duplicate companies (keep the one with highest score)
            # This is a simplified approach
            duplicate_companies = db.execute("""
                SELECT name, COUNT(*) as count 
                FROM companies 
                GROUP BY name 
                HAVING COUNT(*) > 1
            """).fetchall()
            
            for name, count in duplicate_companies:
                # Keep the company with the highest score
                companies = db.query(Company).filter(Company.name == name).order_by(
                    Company.company_score.desc()
                ).all()
                
                # Delete all but the first (highest scored)
                for company in companies[1:]:
                    db.delete(company)
                
                cleanup_results.append(f"Removed {len(companies)-1} duplicate companies for '{name}'")
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            db.rollback()
        
        return cleanup_results
    
    def _update_table_statistics(self, db):
        """Update database table statistics for query optimization"""
        try:
            # For SQLite, run ANALYZE to update statistics
            db.execute("ANALYZE")
            db.commit()
        except Exception as e:
            logger.error(f"Error updating table statistics: {e}")
    
    async def parallel_job_processing(self, job_ids: List[int], processing_func, max_workers: Optional[int] = None) -> List:
        """Process jobs in parallel using thread pool"""
        max_workers = max_workers or self.max_workers
        
        try:
            loop = asyncio.get_event_loop()
            
            # Split job_ids into chunks for parallel processing
            chunk_size = max(1, len(job_ids) // max_workers)
            chunks = [job_ids[i:i + chunk_size] for i in range(0, len(job_ids), chunk_size)]
            
            # Process chunks in parallel
            tasks = []
            for chunk in chunks:
                task = loop.run_in_executor(self.thread_pool, processing_func, chunk)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Flatten results
            flattened_results = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error in parallel processing: {result}")
                elif isinstance(result, list):
                    flattened_results.extend(result)
                else:
                    flattened_results.append(result)
            
            return flattened_results
            
        except Exception as e:
            logger.error(f"Error in parallel job processing: {e}")
            return []
    
    async def batch_database_operations(self, operations: List[Dict], batch_size: int = 100) -> Dict:
        """Execute database operations in optimized batches"""
        try:
            db = self.OptimizedSession()
            
            total_operations = len(operations)
            completed_operations = 0
            errors = []
            
            # Process in batches
            for i in range(0, total_operations, batch_size):
                batch = operations[i:i + batch_size]
                
                try:
                    # Begin transaction
                    db.begin()
                    
                    for operation in batch:
                        op_type = operation.get('type')
                        data = operation.get('data')
                        
                        if op_type == 'insert':
                            db.add(data)
                        elif op_type == 'update':
                            db.merge(data)
                        elif op_type == 'delete':
                            db.delete(data)
                    
                    # Commit batch
                    db.commit()
                    completed_operations += len(batch)
                    
                except Exception as e:
                    db.rollback()
                    errors.append(f"Batch {i//batch_size + 1}: {str(e)}")
                    logger.error(f"Error in batch operation: {e}")
            
            db.close()
            
            return {
                'total_operations': total_operations,
                'completed_operations': completed_operations,
                'errors': errors,
                'success_rate': (completed_operations / total_operations) * 100 if total_operations > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error in batch database operations: {e}")
            return {'error': str(e)}
    
    async def optimize_memory_usage(self) -> Dict:
        """Optimize application memory usage"""
        optimizations = []
        
        try:
            import gc
            
            # Force garbage collection
            collected = gc.collect()
            optimizations.append(f"Garbage collection freed {collected} objects")
            
            # Clear performance metrics history if too large
            for key in ['cpu_usage', 'memory_usage', 'response_times']:
                if len(self.performance_metrics.get(key, [])) > 50:
                    self.performance_metrics[key] = self.performance_metrics[key][-50:]
                    optimizations.append(f"Trimmed {key} history")
            
            # Get memory usage after optimization
            memory = psutil.virtual_memory()
            
            return {
                'status': 'success',
                'optimizations_applied': optimizations,
                'memory_usage_percent': memory.percent,
                'memory_available_gb': round(memory.available / (1024**3), 2)
            }
            
        except Exception as e:
            logger.error(f"Error optimizing memory usage: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_performance_recommendations(self) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []
        
        try:
            # Analyze recent performance metrics
            if self.performance_metrics['cpu_usage']:
                recent_cpu = [m['value'] for m in self.performance_metrics['cpu_usage'][-10:]]
                avg_cpu = sum(recent_cpu) / len(recent_cpu)
                
                if avg_cpu > 80:
                    recommendations.append("High CPU usage detected. Consider scaling horizontally or optimizing algorithms.")
                elif avg_cpu > 60:
                    recommendations.append("Moderate CPU usage. Monitor for potential bottlenecks.")
            
            if self.performance_metrics['memory_usage']:
                recent_memory = [m['value'] for m in self.performance_metrics['memory_usage'][-10:]]
                avg_memory = sum(recent_memory) / len(recent_memory)
                
                if avg_memory > 85:
                    recommendations.append("High memory usage. Consider implementing memory caching strategies.")
                elif avg_memory > 70:
                    recommendations.append("Moderate memory usage. Monitor for memory leaks.")
            
            # Database recommendations
            db_status = self._get_db_pool_status()
            if db_status.get('checked_out', 0) > db_status.get('pool_size', 0) * 0.8:
                recommendations.append("Database connection pool is heavily utilized. Consider increasing pool size.")
            
            # General recommendations
            recommendations.extend([
                "Enable Redis caching for frequently accessed data.",
                "Implement database query optimization and indexing.",
                "Use background jobs for heavy computational tasks.",
                "Monitor and optimize API response times.",
                "Implement horizontal scaling for high traffic periods."
            ])
            
        except Exception as e:
            logger.error(f"Error generating performance recommendations: {e}")
        
        return recommendations
    
    async def health_check(self) -> Dict:
        """Comprehensive application health check"""
        health_status = {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_status': 'healthy',
            'components': {}
        }
        
        try:
            # Database health
            try:
                db = self.OptimizedSession()
                db.execute("SELECT 1")
                db.close()
                health_status['components']['database'] = 'healthy'
            except Exception as e:
                health_status['components']['database'] = f'unhealthy: {str(e)}'
                health_status['overall_status'] = 'degraded'
            
            # System resources
            metrics = await self.get_system_metrics()
            cpu_usage = metrics.get('cpu', {}).get('usage_percent', 0)
            memory_usage = metrics.get('memory', {}).get('used_percent', 0)
            
            if cpu_usage > 90 or memory_usage > 90:
                health_status['overall_status'] = 'critical'
                health_status['components']['system_resources'] = 'critical'
            elif cpu_usage > 70 or memory_usage > 70:
                health_status['overall_status'] = 'degraded'
                health_status['components']['system_resources'] = 'degraded'
            else:
                health_status['components']['system_resources'] = 'healthy'
            
            # Thread pool health
            if self.thread_pool._threads:
                health_status['components']['thread_pool'] = 'healthy'
            else:
                health_status['components']['thread_pool'] = 'degraded'
            
            health_status['metrics'] = metrics
            
        except Exception as e:
            health_status['overall_status'] = 'critical'
            health_status['error'] = str(e)
            logger.error(f"Error in health check: {e}")
        
        return health_status
    
    def shutdown(self):
        """Graceful shutdown of scaling manager"""
        try:
            self.thread_pool.shutdown(wait=True)
            self.process_pool.shutdown(wait=True)
            logger.info("Scaling manager shutdown completed")
        except Exception as e:
            logger.error(f"Error during scaling manager shutdown: {e}")

# Global scaling manager instance
scaling_manager = ScalingManager()
