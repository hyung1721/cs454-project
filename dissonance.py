def parse_metrics(text):
    # Split into lines for processing
    lines = text.split('\n')
    
    # Define our metric types
    cohesion_metrics = ['LSCC', 'TCC', 'CC', 'SCOM', 'LCOM5']
    coupling_metrics = ['CBO', 'RFC', 'DIT']
    measured_pair = []
    
    # Initialize totals
    total_agreement = 0
    total_dissonant = 0
    total_conflicted = 0
    counter = 0
    
    for i in range(len(lines)-1):
        if 'vs' in lines[i]:
            for metric1 in cohesion_metrics:
                if metric1 in lines[i]:
                    for metric2 in coupling_metrics:
                        if metric2 in lines[i]:
                            if (metric1, metric2) not in measured_pair:
                
                                # Parse the numbers from the next line
                                numbers = [int(s.strip(',:')) for s in lines[i+1].split() 
                                        if s.strip(',:').isdigit()]
                                agreement, dissonant, conflicted = numbers
                                total_agreement += agreement
                                total_dissonant += dissonant
                                total_conflicted += conflicted
                                counter += 1
                                measured_pair.append((metric1, metric2))
                                break
                    break
            
                
                
    print("\nTotals:")
    print(f"Total Agreement: {total_agreement}")
    print(f"Total Dissonant: {total_dissonant}")
    print(f"Total Conflicted: {total_conflicted}")
    print(f"Counter: {counter}")
    
    return counter, total_agreement, total_dissonant, total_conflicted
def main():
    # Example usage
    filename = 'log/asciimatics/asciimatics_1000_fix-ver2-paper.log.txt'
    with open(filename, 'r') as file:
        text = file.read()
        
    counter, agreement, dissonant, conflicted = parse_metrics(text)

    with open('results_dissonance.txt', 'a') as output_file:
        output_file.write(f"{filename}::Recorded data count: {str(counter)}\n")
        output_file.write(f"Agreement: {agreement}, Dissonant: {dissonant}, Conflicted: {conflicted}\n")
    output_file.close()

if __name__ == '__main__':
    main()