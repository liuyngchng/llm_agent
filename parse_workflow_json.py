#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

def process_data(data):
    print(f"process_data {data}")
    return ""


def evaluate_condition(data):
    print(f"evaluate_condition {data}")
    return ""

def process_node(node_type, data):
    if node_type == 'data_processing':
        return process_data(data)
    elif node_type == 'condition':
        return evaluate_condition(data)
    return None

def execute_workflow(workflow):
    for node in workflow['nodes']:
        result = process_node(node['type'], node.get('data', {}))
        print(f"Processed node {node['id']} with result: {result}")


if __name__ == "__main__":
    with open('workflow.json', 'r', encoding='utf-8') as file:
        workflow_data = json.load(file)

    print(workflow_data)
    for node in workflow_data['nodes']:
        print(f"Node ID: {node['id']}, Type: {node['type']}")

    for edge in workflow_data['edges']:
        # print(f"From: {edge['from']}, To: {edge['to']}")
        print(f"From: {edge['source']}, To: {edge['target']}")