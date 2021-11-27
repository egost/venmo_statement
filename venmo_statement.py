# To use run: python venmo_statement.py --output output.csv venmo_statement.csv

import pandas as pd
import click

from re import sub
from decimal import Decimal


@click.command()
@click.argument('filepath')
@click.option('--output', '-o')
def main(filepath, output=None):
    click.echo('Processing {} -> {}'.format(filepath, output))
    click.echo()

    # read activity
    df = pd.read_csv(filepath, header=2, skipfooter=10, engine='python')
    df = df.drop(labels=['Unnamed: 0','Disclaimer','Year to Date Venmo Fees'], axis='columns')

    # read initial balance
    def remove_money_format(money):
        amount = str(money)
        sign = -1.0 if amount[0] == '-' else 1.0
        amount = amount.replace(' $', '').replace(',','')
        amount = sign*float(amount[1:])
        return amount

    starting_balance = remove_money_format(df['Beginning Balance'].iloc[0])

    # extract debits and credits for DEBIT CARD
    # I want the Datetime, Type, From + To: Note, Debits (Negative Amount(total)), Credits (Positive Amount(total))

    general_ledger = df[['Datetime', 'Type', 'From', 'To', 'Note', 'Funding Source', 'Amount (total)']].fillna('')
    general_ledger = general_ledger.drop(0) # drop the beginning balance row
    # set datetime to datetime
    general_ledger['Datetime'] = pd.to_datetime(general_ledger['Datetime'])

    def build_description(row):
        if pd.isnull(row['From']) and pd.isnull(row['To']):
            if pd.isnull(row['Note']):
                return ''
            else:
                return row['Note']

        return f"{row['From']} -> {row['To']}: {row['Note']}"

    general_ledger['Description'] = df.apply(lambda row: build_description(row), axis=1)
    # general_ledger = general_ledger.drop(labels=['Note', 'From', 'To'], axis='columns')
    # rename columns
    general_ledger = general_ledger.rename(columns={'Note': 'Memo'})


    # remove credit card entries
    cc_ledger = general_ledger[general_ledger['Type'].str.contains('Credit Card Payment') & ~general_ledger['Funding Source'].str.contains('Venmo balance')]

    general_ledger = general_ledger.drop(cc_ledger.index)
    general_ledger = general_ledger.drop(labels=['Funding Source'], axis='columns')


    def map_debits_credits(row):
        debit, credit = 0.00, 0.00

        if str(row['Amount (total)']) != 'nan':
            amount = remove_money_format(row['Amount (total)'])

            if amount < 0:
                debit = abs(amount)
            elif amount > 0:
                credit = abs(amount)

        row['Debit'] = debit
        row['Credit'] = credit

        return row
    

    general_ledger[['Debit', 'Credit']] = general_ledger.apply(lambda row: map_debits_credits(row), axis=1)[['Debit', 'Credit']]
    general_ledger = general_ledger.drop(labels=['Amount (total)'], axis='columns')

    total_debits = general_ledger.Debit.sum()
    total_credits = general_ledger.Credit.sum()
    ending_balance = starting_balance + total_credits - total_debits

    click.echo(general_ledger.to_markdown(floatfmt='>8.2f'))
    click.echo()
    click.echo(f'Total Transactions:   {len(general_ledger.index):>8.0f}')
    click.echo()
    click.echo(f'Starting Balance:   $ {starting_balance:>8.2f}')
    click.echo(f'Total Debits:       $ {total_debits:>8.2f}')
    click.echo(f'Total Credits:      $ {total_credits:>8.2f}')
    click.echo(f'Ending Balance:     $ {ending_balance:>8.2f}')
    click.echo()

    # create new column for sum of credits and debits
    # prep for YNAB
    general_ledger['Amount'] = -general_ledger.Debit + general_ledger.Credit
    # convert datetime to date
    general_ledger['Date'] = general_ledger.Datetime.dt.date
    general_ledger.to_csv(output, index=False)


    # TODO: read crypto summary


if __name__ == "__main__":
    main()
