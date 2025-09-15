import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from streamlit_app.common import DB_PATH
from agents.rlhf_tracker import RLHFTracker
from agents.feedback_processor import FeedbackProcessor
from agents.keyword_extractor import KeywordExtractor

st.set_page_config(page_title="RLHF Analytics", page_icon="📊", layout="wide")


# Initialize components
@st.cache_resource
def get_components():
    return {
        "rlhf_tracker": RLHFTracker(),
        "feedback_processor": FeedbackProcessor(),
        "keyword_extractor": KeywordExtractor(),
    }


components = get_components()

st.title("📊 RLHF Analytics Dashboard")
st.markdown("**Reinforcement Learning from Human Feedback - Job Search Optimization**")

# Sidebar controls
st.sidebar.header("Analytics Controls")
lookback_days = st.sidebar.slider("Lookback Days", 7, 365, 90)
min_sample_size = st.sidebar.slider("Minimum Sample Size", 1, 20, 5)

# Refresh data button
if st.sidebar.button("Refresh Analytics", type="primary"):
    st.cache_data.clear()
    st.rerun()

# Main analytics sections
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "📈 Success Metrics",
        "🔍 Keyword Analysis",
        "💡 Recommendations",
        "📊 Performance Trends",
        "🎯 Pattern Learning",
    ]
)

# Tab 1: Success Metrics
with tab1:
    st.header("Application Success Metrics")

    # Get success metrics
    @st.cache_data(ttl=300)  # Cache for 5 minutes
    def get_success_metrics(days):
        return components["rlhf_tracker"].get_job_success_metrics(days)

    metrics = get_success_metrics(lookback_days)

    if metrics and metrics.get("overall"):
        overall = metrics["overall"]

        # Display key metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Applications", int(overall.get("total_applications", 0)))

        with col2:
            avg_success = overall.get("avg_success_score", 0) or 0
            st.metric(
                "Avg Success Score",
                f"{avg_success:.2f}",
                f"{(avg_success - 0.5) * 100:+.1f}%",
            )

        with col3:
            positive_responses = overall.get("positive_responses", 0) or 0
            total_apps = overall.get("total_applications", 1) or 1
            response_rate = (positive_responses / total_apps) * 100
            st.metric("Response Rate", f"{response_rate:.1f}%")

        with col4:
            avg_response_time = overall.get("avg_response_time", 0) or 0
            st.metric("Avg Response Time", f"{avg_response_time:.1f} days")

        # Success by company type
        if metrics.get("by_company_type"):
            st.subheader("Success Rate by Company Type")

            company_df = pd.DataFrame(metrics["by_company_type"])
            if not company_df.empty:
                company_df = company_df.dropna(subset=["company_type"])

                fig = px.bar(
                    company_df,
                    x="company_type",
                    y="avg_success_score",
                    title="Average Success Score by Company Type",
                    color="avg_success_score",
                    color_continuous_scale="RdYlGn",
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

        # Top successful keywords
        if metrics.get("successful_keywords"):
            st.subheader("Most Successful Keywords")

            keywords_df = pd.DataFrame(metrics["successful_keywords"])
            if not keywords_df.empty:
                # Display top 15 keywords
                top_keywords = keywords_df.head(15)

                fig = px.scatter(
                    top_keywords,
                    x="frequency",
                    y="avg_success_score",
                    size="frequency",
                    color="category",
                    hover_data=["keyword"],
                    title="Keyword Frequency vs Success Rate",
                )
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)

                # Show table
                st.dataframe(
                    top_keywords[
                        ["keyword", "category", "frequency", "avg_success_score"]
                    ].round(3),
                    use_container_width=True,
                )
    else:
        st.info(
            "No application outcome data available yet. Apply to some jobs to see analytics!"
        )

# Tab 2: Keyword Analysis
with tab2:
    st.header("Keyword Analysis")

    # Keyword category selector
    category_filter = st.selectbox(
        "Filter by Category",
        ["All"]
        + ["ai_ml", "tech_stack", "seniority", "domain", "soft_skills", "company_type"],
    )

    category = None if category_filter == "All" else category_filter

    # Get trending keywords
    @st.cache_data(ttl=300)
    def get_trending_keywords(days, cat):
        return components["keyword_extractor"].get_trending_keywords(days, cat)

    trending = get_trending_keywords(lookback_days, category)

    if trending:
        st.subheader(f"Trending Keywords (Last {lookback_days} days)")

        trending_df = pd.DataFrame(trending)

        # Keywords trending chart
        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Frequency Distribution",
                "Job Score Distribution",
                "Category Breakdown",
                "Frequency vs Score",
            ),
            specs=[
                [{"type": "histogram"}, {"type": "histogram"}],
                [{"type": "pie"}, {"type": "scatter"}],
            ],
        )

        # Frequency histogram
        fig.add_trace(
            go.Histogram(x=trending_df["recent_frequency"], name="Frequency"),
            row=1,
            col=1,
        )

        # Job score histogram
        fig.add_trace(
            go.Histogram(x=trending_df["avg_job_score"].dropna(), name="Job Score"),
            row=1,
            col=2,
        )

        # Category pie chart
        category_counts = trending_df["category"].value_counts()
        fig.add_trace(
            go.Pie(
                labels=category_counts.index,
                values=category_counts.values,
                name="Categories",
            ),
            row=2,
            col=1,
        )

        # Frequency vs Score scatter
        fig.add_trace(
            go.Scatter(
                x=trending_df["recent_frequency"],
                y=trending_df["avg_job_score"],
                mode="markers",
                text=trending_df["keyword"],
                name="Keywords",
            ),
            row=2,
            col=2,
        )

        fig.update_layout(height=800, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        # Show trending keywords table
        display_columns = [
            "keyword",
            "category",
            "recent_frequency",
            "recent_jobs",
            "avg_job_score",
        ]
        available_columns = [
            col for col in display_columns if col in trending_df.columns
        ]

        st.dataframe(
            trending_df[available_columns].head(20).round(2), use_container_width=True
        )
    else:
        st.info("No trending keywords found for the selected period and category.")

# Tab 3: Recommendations
with tab3:
    st.header("AI-Generated Recommendations")

    # Get recommendations
    @st.cache_data(ttl=300)
    def get_recommendations():
        return components["feedback_processor"].get_recommendations(limit=20)

    recommendations = get_recommendations()

    if recommendations:
        st.subheader("Top Targeting Recommendations")

        for i, rec in enumerate(recommendations[:10], 1):
            with st.expander(f"{i}. {rec['description']}", expanded=i <= 3):
                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Success Rate", f"{rec['success_rate']:.1%}")
                    st.metric("Confidence", f"{rec['confidence']:.1%}")

                with col2:
                    st.metric("Priority Score", f"{rec['priority']:.2f}")
                    st.metric("Sample Size", rec["sample_size"])

                # Show pattern details
                st.subheader("Pattern Details")
                details = rec["details"]

                if rec["type"] == "keyword_combo":
                    st.write(f"**Keyword:** {details.get('keyword', 'N/A')}")
                    st.write(f"**Category:** {details.get('category', 'N/A')}")
                    st.write(
                        f"**Avg Response Time:** {details.get('avg_response_time', 0):.1f} days"
                    )

                elif rec["type"] == "company_trait":
                    st.write(f"**Company Type:** {details.get('company_type', 'N/A')}")
                    st.write(f"**Company Size:** {details.get('company_size', 'N/A')}")
                    st.write(
                        f"**PE Portfolio:** {details.get('is_pe_portfolio', False)}"
                    )

                elif rec["type"] == "job_characteristic":
                    st.write(f"**Job Type:** {details.get('job_type', 'N/A')}")
                    st.write(
                        f"**Experience Level:** {details.get('experience_level', 'N/A')}"
                    )
                    st.write(
                        f"**Remote Friendly:** {details.get('remote_friendly', False)}"
                    )
                    st.write(
                        f"**Score Category:** {details.get('score_category', 'N/A')}"
                    )

        # Recommendations summary chart
        if len(recommendations) >= 5:
            rec_df = pd.DataFrame(
                [
                    {
                        "description": rec["description"][:50] + "..."
                        if len(rec["description"]) > 50
                        else rec["description"],
                        "success_rate": rec["success_rate"],
                        "confidence": rec["confidence"],
                        "priority": rec["priority"],
                        "type": rec["type"],
                    }
                    for rec in recommendations[:10]
                ]
            )

            fig = px.scatter(
                rec_df,
                x="confidence",
                y="success_rate",
                size="priority",
                color="type",
                hover_data=["description"],
                title="Recommendation Priority Matrix",
            )
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.info(
            "No recommendations available yet. Need more application outcome data to generate patterns."
        )

# Tab 4: Performance Trends
with tab4:
    st.header("Performance Trends")

    # Get performance trends
    @st.cache_data(ttl=300)
    def get_performance_trends(days):
        return components["feedback_processor"].analyze_performance_trends(days)

    trends = get_performance_trends(lookback_days)

    if trends and trends.get("daily_metrics"):
        daily_metrics = pd.DataFrame(trends["daily_metrics"])
        daily_metrics["date"] = pd.to_datetime(daily_metrics["date"])

        # Key trend metrics
        col1, col2, col3 = st.columns(3)

        with col1:
            success_trend = trends.get("success_trend", 0)
            st.metric(
                "Success Trend", f"{success_trend:+.1%}", delta=f"{success_trend:+.1%}"
            )

        with col2:
            response_trend = trends.get("response_time_trend", 0)
            st.metric(
                "Response Time Trend",
                f"{response_trend:+.1%}",
                delta=f"{response_trend:+.1%}",
                delta_color="inverse",
            )

        with col3:
            total_apps = trends.get("total_applications", 0)
            st.metric("Total Applications", total_apps)

        # Performance charts
        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Daily Applications",
                "Success Score Trend",
                "Response Time",
                "Positive Outcomes",
            ),
            specs=[
                [{"secondary_y": False}, {"secondary_y": False}],
                [{"secondary_y": False}, {"secondary_y": False}],
            ],
        )

        # Daily applications
        fig.add_trace(
            go.Scatter(
                x=daily_metrics["date"],
                y=daily_metrics["applications"],
                mode="lines+markers",
                name="Applications",
                line=dict(color="blue"),
            ),
            row=1,
            col=1,
        )

        # Success score trend
        fig.add_trace(
            go.Scatter(
                x=daily_metrics["date"],
                y=daily_metrics["avg_success"],
                mode="lines+markers",
                name="Success Score",
                line=dict(color="green"),
            ),
            row=1,
            col=2,
        )

        # Response time
        if "avg_response_time" in daily_metrics.columns:
            fig.add_trace(
                go.Scatter(
                    x=daily_metrics["date"],
                    y=daily_metrics["avg_response_time"],
                    mode="lines+markers",
                    name="Response Time",
                    line=dict(color="orange"),
                ),
                row=2,
                col=1,
            )

        # Positive outcomes
        fig.add_trace(
            go.Scatter(
                x=daily_metrics["date"],
                y=daily_metrics["positive_outcomes"],
                mode="lines+markers",
                name="Positive Outcomes",
                line=dict(color="red"),
            ),
            row=2,
            col=2,
        )

        fig.update_layout(height=700, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        # Show daily metrics table
        st.subheader("Daily Metrics Details")
        st.dataframe(daily_metrics.round(2), use_container_width=True)
    else:
        st.info("No performance trend data available yet.")

# Tab 5: Pattern Learning
with tab5:
    st.header("Pattern Learning Status")

    # Get learned patterns
    @st.cache_data(ttl=300)
    def get_learned_patterns():
        return components["rlhf_tracker"].get_active_patterns(min_confidence=0.5)

    patterns = get_learned_patterns()

    if patterns:
        st.subheader(f"Active Learned Patterns ({len(patterns)} total)")

        # Pattern type distribution
        pattern_df = pd.DataFrame(patterns)

        col1, col2 = st.columns(2)

        with col1:
            type_counts = pattern_df["pattern_type"].value_counts()
            fig = px.pie(
                values=type_counts.values,
                names=type_counts.index,
                title="Pattern Types Distribution",
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.scatter(
                pattern_df,
                x="confidence_level",
                y="success_rate",
                size="sample_size",
                color="pattern_type",
                title="Pattern Confidence vs Success Rate",
            )
            st.plotly_chart(fig, use_container_width=True)

        # Pattern details table
        st.subheader("Pattern Details")

        display_df = pattern_df[
            [
                "pattern_type",
                "pattern_description",
                "success_rate",
                "confidence_level",
                "sample_size",
                "last_validated",
            ]
        ].copy()

        display_df["success_rate"] = display_df["success_rate"].round(3)
        display_df["confidence_level"] = display_df["confidence_level"].round(3)

        st.dataframe(display_df, use_container_width=True)

        # Pattern effectiveness over time
        if "last_validated" in pattern_df.columns:
            pattern_df["last_validated"] = pd.to_datetime(pattern_df["last_validated"])

            fig = px.timeline(
                pattern_df.head(10),
                x_start="last_validated",
                x_end="last_validated",
                y="pattern_description",
                color="success_rate",
                title="Recent Pattern Learning Activity",
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(
            "No learned patterns available yet. The system will learn patterns as more application data is collected."
        )

# Footer
st.markdown("---")
st.markdown(
    "**RLHF Analytics Dashboard** - Tracks application outcomes and learns patterns to improve job targeting. "
    "Data refreshes automatically every 5 minutes."
)
