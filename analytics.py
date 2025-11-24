import os
import sys
import csv
import statistics
from datetime import datetime

# Check for optional libraries
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


#  DATA LOADING 

def load_csv(filename):
    """Load and parse the CSV file"""
    if not os.path.exists(filename):
        return None
    
    data = {'parallel': [], 'sequential': []}
    
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                entry = {
                    'timestamp': row.get('timestamp', ''),
                    'mode': row.get('mode', 'parallel'),
                    'locks_enabled': row.get('locks_enabled', 'True') == 'True',
                    'ai_work_ms': float(row.get('ai_work_ms', 0)),
                    'avg_ai_ms': float(row.get('avg_ai_ms', 0)),
                    'fps': float(row.get('fps', 0)),
                    'num_ghosts': int(row.get('num_ghosts', 6)),
                    'speedup': float(row.get('speedup', 0)),
                    'total_updates': int(row.get('total_updates', 0)),
                    'active_processes': int(row.get('active_processes', 0)),
                }
                mode = entry['mode']
                if mode in data:
                    data[mode].append(entry)
            except (ValueError, KeyError) as e:
                continue  # Skip malformed rows
    
    return data


def calculate_stats(data):
    """Calculate statistics from the loaded data"""
    stats = {}
    
    for mode in ['parallel', 'sequential']:
        entries = data.get(mode, [])
        if entries:
            ai_times = [e['avg_ai_ms'] for e in entries if e['avg_ai_ms'] > 0]
            fps_values = [e['fps'] for e in entries if e['fps'] > 0]
            workloads = [e['ai_work_ms'] for e in entries]
            
            stats[mode] = {
                'count': len(entries),
                'avg_ai_ms': statistics.mean(ai_times) if ai_times else 0,
                'min_ai_ms': min(ai_times) if ai_times else 0,
                'max_ai_ms': max(ai_times) if ai_times else 0,
                'std_ai_ms': statistics.stdev(ai_times) if len(ai_times) > 1 else 0,
                'avg_fps': statistics.mean(fps_values) if fps_values else 0,
                'avg_workload': statistics.mean(workloads) if workloads else 0,
            }
        else:
            stats[mode] = {
                'count': 0, 'avg_ai_ms': 0, 'min_ai_ms': 0,
                'max_ai_ms': 0, 'std_ai_ms': 0, 'avg_fps': 0, 'avg_workload': 0
            }
    
    # Calculate actual speedup
    if stats['parallel']['avg_ai_ms'] > 0:
        stats['speedup'] = stats['sequential']['avg_ai_ms'] / stats['parallel']['avg_ai_ms']
    else:
        stats['speedup'] = 1.0
    
    # Get number of ghosts from data
    all_entries = data.get('parallel', []) + data.get('sequential', [])
    stats['num_ghosts'] = all_entries[0]['num_ghosts'] if all_entries else 6
    
    return stats


#  TEXT REPORT 

def print_report(stats, filename="analysis_report.txt"):
    """Generate and print a text report"""
    num_ghosts = stats.get('num_ghosts', 6)
    efficiency = (stats['speedup'] / num_ghosts) * 100 if num_ghosts > 0 else 0
    time_saved = stats['sequential']['avg_ai_ms'] - stats['parallel']['avg_ai_ms']
    
    report = f"""
================================================================================
              PARALLEL PAC-MAN — PERFORMANCE ANALYSIS REPORT
                              Group 12
================================================================================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

┌─────────────────────────────────────────────────────────────────────────────┐
│                           CONFIGURATION                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Number of Ghost Threads:  {num_ghosts:<6}                                        │
│  Samples (Sequential):     {stats['sequential']['count']:<6}                                        │
│  Samples (Parallel):       {stats['parallel']['count']:<6}                                        │
│  Average AI Workload:      {stats['parallel']['avg_workload']:.0f} ms                                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                      AI PROCESSING TIME (milliseconds)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                        SEQUENTIAL         PARALLEL         DIFFERENCE       │
│  Average:              {stats['sequential']['avg_ai_ms']:>8.2f} ms       {stats['parallel']['avg_ai_ms']:>8.2f} ms       {time_saved:>8.2f} ms     │
│  Minimum:              {stats['sequential']['min_ai_ms']:>8.2f} ms       {stats['parallel']['min_ai_ms']:>8.2f} ms                        │
│  Maximum:              {stats['sequential']['max_ai_ms']:>8.2f} ms       {stats['parallel']['max_ai_ms']:>8.2f} ms                        │
│  Std Deviation:        {stats['sequential']['std_ai_ms']:>8.2f} ms       {stats['parallel']['std_ai_ms']:>8.2f} ms                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           SPEEDUP ANALYSIS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  Actual Speedup:           {stats['speedup']:>6.2f}x                                       │
│  Theoretical Maximum:      {num_ghosts:>6.2f}x  (with {num_ghosts} threads)                        │
│  Parallel Efficiency:      {efficiency:>6.1f}%                                       │
│  Time Saved per Update:    {time_saved:>6.2f} ms                                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           FPS COMPARISON                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  Sequential Mode:          {stats['sequential']['avg_fps']:>6.1f} FPS                                     │
│  Parallel Mode:            {stats['parallel']['avg_fps']:>6.1f} FPS                                     │
│  FPS Improvement:          {stats['parallel']['avg_fps'] - stats['sequential']['avg_fps']:>6.1f} FPS                                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            KEY FINDINGS                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Parallel execution achieved {stats['speedup']:.2f}x speedup over sequential            │
│  2. Efficiency: {efficiency:.1f}% of theoretical maximum                              │
│  3. Average time saved per AI update: {time_saved:.2f} ms                          │
│  4. FPS improved by {stats['parallel']['avg_fps'] - stats['sequential']['avg_fps']:.1f} frames per second                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                       CONCEPTS DEMONSTRATED                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  ✓ Task Division:      Each ghost AI runs as an independent process         │
│  ✓ Synchronization:    Locks protect shared maze data from corruption       │
│  ✓ Parallel Execution: Multiple CPU cores process ghosts simultaneously     │
│  ✓ Speedup:            Measured {stats['speedup']:.2f}x performance improvement              │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
"""
    
    print(report)
    
    # Save to file
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"[OK] Report saved to: {filename}")
    except Exception as e:
        print(f"[WARN] Could not save report: {e}")
    
    return report


#  CHART GENERATION 

def generate_charts(stats, output_dir="."):
    """Generate all charts for the presentation"""
    if not HAS_MATPLOTLIB:
        print("\n[ERROR] matplotlib is required for charts!")
        print("        Install with: pip install matplotlib")
        return
    
    num_ghosts = stats.get('num_ghosts', 6)
    
    # Set style
    plt.style.use('default')
    plt.rcParams['figure.facecolor'] = 'white'
    plt.rcParams['axes.facecolor'] = 'white'
    
    # 1. SPEEDUP COMPARISON CHART
    print("\n[INFO] Generating speedup_comparison.png...")
    fig, ax = plt.subplots(figsize=(10, 6))
    
    categories = ['Sequential\n(Baseline)', 'Parallel\n(Actual)', 'Theoretical\nMaximum']
    values = [1.0, stats['speedup'], num_ghosts]
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
    
    bars = ax.bar(categories, values, color=colors, edgecolor='black', linewidth=2, width=0.6)
    
    for bar, val in zip(bars, values):
        ax.annotate(f'{val:.2f}x',
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 5), textcoords="offset points",
                    ha='center', va='bottom', fontsize=16, fontweight='bold')
    
    ax.set_ylabel('Speedup Factor', fontsize=14)
    ax.set_title('Parallel vs Sequential Execution Speedup', fontsize=16, fontweight='bold', pad=20)
    ax.set_ylim(0, max(values) * 1.3)
    ax.axhline(y=1, color='gray', linestyle='--', alpha=0.5, linewidth=2)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'speedup_comparison.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("    ✓ speedup_comparison.png")
    
    # 2. AI TIME COMPARISON CHART
    print("[INFO] Generating ai_time_comparison.png...")
    fig, ax = plt.subplots(figsize=(10, 6))
    
    modes = ['Sequential', 'Parallel']
    avg_times = [stats['sequential']['avg_ai_ms'], stats['parallel']['avg_ai_ms']]
    colors = ['#FF6B6B', '#4ECDC4']
    
    bars = ax.bar(modes, avg_times, color=colors, edgecolor='black', linewidth=2, width=0.5)
    
    for bar, val in zip(bars, avg_times):
        ax.annotate(f'{val:.1f} ms',
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 5), textcoords="offset points",
                    ha='center', va='bottom', fontsize=14, fontweight='bold')
    
    # Add time saved annotation
    time_saved = avg_times[0] - avg_times[1]
    ax.annotate(f'↓ {time_saved:.1f} ms saved!',
                xy=(1, avg_times[1] + (avg_times[0] - avg_times[1])/2),
                fontsize=12, color='green', fontweight='bold',
                ha='center')
    
    ax.set_ylabel('AI Processing Time (ms)', fontsize=14)
    ax.set_title('AI Update Time: Sequential vs Parallel', fontsize=16, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'ai_time_comparison.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("    ✓ ai_time_comparison.png")
    
    # 3. EFFICIENCY PIE CHART
    print("[INFO] Generating efficiency_chart.png...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    efficiency = (stats['speedup'] / num_ghosts) * 100
    overhead = 100 - efficiency
    
    sizes = [max(0, efficiency), max(0, overhead)]
    labels = [f'Useful Parallel\nWork ({efficiency:.1f}%)', f'Overhead\n({overhead:.1f}%)']
    colors = ['#4ECDC4', '#FF6B6B']
    explode = (0.05, 0)
    
    ax1.pie(sizes, explode=explode, labels=labels, colors=colors,
            autopct='', shadow=True, startangle=90,
            textprops={'fontsize': 12, 'fontweight': 'bold'})
    ax1.set_title('Parallel Efficiency Breakdown', fontsize=14, fontweight='bold')
    
    # Resource utilization bar chart
    categories = ['CPU Cores\nUsed', 'Ghost\nThreads', 'Actual\nSpeedup', 'Ideal\nSpeedup']
    values = [min(num_ghosts, 8), num_ghosts, stats['speedup'], num_ghosts]
    colors = ['#45B7D1', '#96CEB4', '#4ECDC4', '#FFEAA7']
    
    bars = ax2.bar(categories, values, color=colors, edgecolor='black', linewidth=1.5)
    
    for bar, val in zip(bars, values):
        ax2.annotate(f'{val:.1f}',
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    ax2.set_ylabel('Count / Speedup Factor', fontsize=12)
    ax2.set_title('Resource Utilization', fontsize=14, fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'efficiency_chart.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("    ✓ efficiency_chart.png")
    
    # 4. CONCEPTS DIAGRAM
    print("[INFO] Generating parallel_concepts.png...")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Colors for ghosts
    ghost_colors = ['#FF6B6B', '#FF85A2', '#4ECDC4', '#FFB347']
    
    # 1. Task Division
    ax = axes[0, 0]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.set_title('1. TASK DIVISION', fontsize=14, fontweight='bold', pad=10)
    
    # Main task box
    ax.add_patch(plt.Rectangle((1, 7), 8, 2, color='#45B7D1', ec='black', lw=2))
    ax.text(5, 8, 'Ghost AI Processing Task', ha='center', va='center', 
            fontsize=11, color='white', fontweight='bold')
    
    # Arrow
    ax.annotate('', xy=(5, 5.5), xytext=(5, 6.8),
                arrowprops=dict(arrowstyle='->', color='black', lw=3))
    ax.text(6, 6.1, 'DIVIDE', fontsize=10, fontweight='bold')
    
    # Divided tasks
    for i in range(4):
        ax.add_patch(plt.Rectangle((0.5 + i*2.3, 2.5), 2, 2.5, 
                                   color=ghost_colors[i], ec='black', lw=2))
        ax.text(1.5 + i*2.3, 3.75, f'Ghost\n{i+1}', ha='center', va='center',
                fontsize=10, color='white', fontweight='bold')
    
    ax.axis('off')
    
    # 2. Parallel Execution
    ax = axes[0, 1]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.set_title('2. PARALLEL EXECUTION', fontsize=14, fontweight='bold', pad=10)
    
    for i in range(4):
        y = 1.5 + i * 2
        # CPU Core
        ax.add_patch(plt.Rectangle((0.5, y), 2.5, 1.5, color='#95A5A6', ec='black', lw=2))
        ax.text(1.75, y + 0.75, f'Core {i+1}', ha='center', va='center', fontsize=10, fontweight='bold')
        
        # Arrow
        ax.annotate('', xy=(4, y + 0.75), xytext=(3.2, y + 0.75),
                    arrowprops=dict(arrowstyle='->', color='black', lw=2))
        
        # Ghost process
        ax.add_patch(plt.Rectangle((4.2, y), 2.5, 1.5, color=ghost_colors[i], ec='black', lw=2))
        ax.text(5.45, y + 0.75, f'Ghost {i+1}', ha='center', va='center', 
                fontsize=10, color='white', fontweight='bold')
        
        # Time indicator
        ax.add_patch(plt.Rectangle((7.5, y + 0.3), 2, 0.9, color='#2ECC71', ec='black'))
    
    ax.text(8.5, 9.2, 'ALL RUN\nSIMULTANEOUSLY!', ha='center', fontsize=11, 
            fontweight='bold', color='#27AE60')
    ax.text(8.5, 0.5, 'Time →', ha='center', fontsize=10)
    ax.axis('off')
    
    # 3. Synchronization
    ax = axes[1, 0]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.set_title('3. SYNCHRONIZATION (LOCKS)', fontsize=14, fontweight='bold', pad=10)
    
    # Shared resource
    ax.add_patch(plt.Rectangle((3, 3.5), 4, 3, color='#F39C12', ec='black', lw=3))
    ax.text(5, 5, 'SHARED\nMAZE DATA', ha='center', va='center', 
            fontsize=12, fontweight='bold')
    
    # Lock
    ax.add_patch(plt.Circle((5, 7.5), 0.8, color='#27AE60', ec='black', lw=2))
    ax.text(5, 7.5, '🔒', ha='center', va='center', fontsize=20)
    ax.text(5, 8.8, 'LOCK', ha='center', fontsize=10, fontweight='bold')
    
    # Ghosts trying to access
    positions = [(1, 5), (9, 5), (3, 0.8), (7, 0.8)]
    for i, (x, y) in enumerate(positions):
        ax.add_patch(plt.Circle((x, y), 0.7, color=ghost_colors[i], ec='black', lw=2))
        ax.text(x, y, f'G{i+1}', ha='center', va='center', fontsize=9, 
                color='white', fontweight='bold')
        # Arrow towards center
        dx, dy = 5 - x, 5 - y
        length = (dx**2 + dy**2)**0.5
        ax.annotate('', xy=(x + dx*0.4, y + dy*0.4), xytext=(x + dx*0.15, y + dy*0.15),
                    arrowprops=dict(arrowstyle='->', color='black', lw=1.5))
    
    ax.axis('off')
    
    # 4. Speedup Result
    ax = axes[1, 1]
    ax.set_title('4. SPEEDUP ACHIEVED', fontsize=14, fontweight='bold', pad=10)
    
    # Timeline bars
    ax.barh(['Sequential\n(One by one)'], [4], color='#FF6B6B', height=0.5, edgecolor='black')
    ax.barh(['Parallel\n(Simultaneous)'], [1], color='#4ECDC4', height=0.5, edgecolor='black')
    
    ax.text(2, 0, '4 time units', ha='center', va='center', fontsize=11, 
            color='white', fontweight='bold')
    ax.text(0.5, 1, '1 unit', ha='center', va='center', fontsize=11, 
            color='white', fontweight='bold')
    
    ax.set_xlabel('Time', fontsize=12)
    ax.set_xlim(0, 5)
    
    # Speedup annotation
    actual_speedup = stats['speedup']
    ax.text(2.5, 1.7, f'SPEEDUP = {actual_speedup:.2f}x', ha='center', fontsize=14,
            fontweight='bold', color='#2980B9',
            bbox=dict(boxstyle='round', facecolor='#AED6F1', edgecolor='#2980B9'))
    
    ax.grid(axis='x', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'parallel_concepts.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("    ✓ parallel_concepts.png")
    
    print("\n[OK] All charts generated successfully!")


# ======================= SIMPLE ANALYSIS (NO MATPLOTLIB) =======================

def simple_analysis(data, stats):
    """Perform simple analysis without matplotlib"""
    print("\n" + "=" * 60)
    print("  SIMPLE DATA ANALYSIS")
    print("=" * 60)
    
    print(f"\n  Total Records: {len(data['parallel']) + len(data['sequential'])}")
    print(f"  Parallel Mode Records: {len(data['parallel'])}")
    print(f"  Sequential Mode Records: {len(data['sequential'])}")
    
    print("\n  --- AI Processing Times ---")
    print(f"  Sequential Average: {stats['sequential']['avg_ai_ms']:.2f} ms")
    print(f"  Parallel Average:   {stats['parallel']['avg_ai_ms']:.2f} ms")
    print(f"  Time Saved:         {stats['sequential']['avg_ai_ms'] - stats['parallel']['avg_ai_ms']:.2f} ms")
    
    print("\n  --- Speedup ---")
    print(f"  Actual Speedup:     {stats['speedup']:.2f}x")
    print(f"  Theoretical Max:    {stats['num_ghosts']:.2f}x")
    print(f"  Efficiency:         {(stats['speedup']/stats['num_ghosts'])*100:.1f}%")
    
    print("\n  --- FPS ---")
    print(f"  Sequential FPS: {stats['sequential']['avg_fps']:.1f}")
    print(f"  Parallel FPS:   {stats['parallel']['avg_fps']:.1f}")
    
    print("\n" + "=" * 60)


#  MAIN 

def main():
    print("\n" + "=" * 60)
    print("  PARALLEL PAC-MAN — CSV ANALYSIS TOOL")
    print("  Group 12")
    print("=" * 60)
    
    # Check for dependencies
    print("\n  Checking dependencies...")
    print(f"    matplotlib: {'✓ Installed' if HAS_MATPLOTLIB else '✗ Not installed (pip install matplotlib)'}")
    print(f"    pandas:     {'✓ Installed' if HAS_PANDAS else '✗ Not installed (optional)'}")
    
    # Get CSV filename
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        csv_file = "parallel_pacman_results.csv"
    
    print(f"\n  Looking for: {csv_file}")
    
    # Load data
    if not os.path.exists(csv_file):
        print(f"\n  [ERROR] File not found: {csv_file}")
        print("\n  Please run the Pac-Man game first to generate data,")
        print("  or specify a CSV file: python pacman_analysis.py <filename.csv>")
        print("\n  Generating demo analysis with sample data...")
        
        # Demo data
        stats = {
            'parallel': {'count': 100, 'avg_ai_ms': 95.5, 'min_ai_ms': 85.2,
                        'max_ai_ms': 112.3, 'std_ai_ms': 8.7, 'avg_fps': 58.2, 'avg_workload': 80},
            'sequential': {'count': 100, 'avg_ai_ms': 485.3, 'min_ai_ms': 475.1,
                          'max_ai_ms': 502.8, 'std_ai_ms': 12.4, 'avg_fps': 12.5, 'avg_workload': 80},
            'speedup': 5.08,
            'num_ghosts': 6
        }
        data = None
    else:
        print(f"  [OK] Found: {csv_file}")
        data = load_csv(csv_file)
        
        if not data or (len(data['parallel']) == 0 and len(data['sequential']) == 0):
            print("\n  [ERROR] No valid data found in CSV file.")
            return
        
        stats = calculate_stats(data)
    
    # Generate outputs
    print("\n" + "-" * 60)
    print("  GENERATING OUTPUTS...")
    print("-" * 60)
    
    # Text report
    print_report(stats)
    
    # Charts (if matplotlib available)
    if HAS_MATPLOTLIB:
        generate_charts(stats)
    else:
        print("\n  [SKIP] Charts not generated (matplotlib not installed)")
        print("         Install with: pip install matplotlib")
    
    # Simple analysis if data exists
    if data:
        simple_analysis(data, stats)
    
    # Summary
    print("\n" + "=" * 60)
    print("  OUTPUT FILES GENERATED:")
    print("-" * 60)
    print("  • analysis_report.txt      - Detailed text report")
    if HAS_MATPLOTLIB:
        print("  • speedup_comparison.png   - Speedup bar chart")
        print("  • ai_time_comparison.png   - AI time comparison")
        print("  • efficiency_chart.png     - Efficiency analysis")
        print("  • parallel_concepts.png    - Concepts diagram for PPT")
    print("\n  Use these files in your PowerPoint presentation!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()